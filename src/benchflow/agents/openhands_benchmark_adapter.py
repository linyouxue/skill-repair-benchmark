"""OpenHands launcher adapter used by the shared benchmark executor.

This file is copied verbatim into the task sandbox and executed by the pinned
OpenHands uv-tool interpreter.  Keep it standalone: the sandbox does not have
the host ``benchflow`` package on its Python path.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping
from functools import wraps
from pathlib import Path
from typing import Any

ENV_MAX_ITERATIONS = "BENCHMARK_EXECUTOR_MAX_ITERATIONS"
ENV_SKILLS_ROOT = "BENCHMARK_EXECUTOR_SKILLS_ROOT"
ENV_SKILLS_SHA256 = "BENCHMARK_EXECUTOR_SKILLS_SHA256"
ENV_SKILL_COUNT = "BENCHMARK_EXECUTOR_SKILL_COUNT"
ENV_BUNDLE_FILE_COUNT = "BENCHMARK_EXECUTOR_BUNDLE_FILE_COUNT"
ENV_DISABLE_SUBAGENTS = "BENCHFLOW_OPENHANDS_DISABLE_SUBAGENTS"

# OpenHands 1.28.1 configures current delegation with the ``task_tool_set``
# specification, which resolves lazily to the provider-facing ``task`` tool.
# Persisted conversations can still use the legacy ``delegate`` specification.
# Keep specification and runtime names separate so filtering cannot confuse the
# factory name with the tool ultimately exposed to the model.
DELEGATION_TOOL_SPEC_NAMES = frozenset({"task_tool_set", "task", "delegate"})
DELEGATION_RUNTIME_TOOL_NAMES = frozenset({"task", "delegate"})

PRELOAD_START = "<BENCHMARK_EXECUTOR_PRELOADED_TASK_SKILLS>"
PRELOAD_END = "</BENCHMARK_EXECUTOR_PRELOADED_TASK_SKILLS>"

_PATCHED = False


def _positive_int(env: Mapping[str, str], key: str) -> int:
    raw = env.get(key, "")
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{key} must be a positive integer, got {raw!r}") from exc
    if value <= 0:
        raise RuntimeError(f"{key} must be a positive integer, got {raw!r}")
    return value


def _regular_bundle_files(root: Path) -> list[tuple[str, bytes]]:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise RuntimeError(f"executor skill root is not a directory: {root}")
    files: list[tuple[str, bytes]] = []
    for path in sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix()):
        relative = path.relative_to(root)
        if path.is_symlink() or any(
            (root / parent).is_symlink() for parent in relative.parents if parent.parts
        ):
            raise RuntimeError(f"executor skill bundle contains symlink: {relative}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise RuntimeError(
                f"executor skill bundle contains non-regular file: {relative}"
            )
        if not path.resolve(strict=True).is_relative_to(root):
            raise RuntimeError(f"executor skill file escapes bundle: {relative}")
        files.append((relative.as_posix(), path.read_bytes()))
    return files


def _bundle_digest(files: list[tuple[str, bytes]]) -> str:
    digest = hashlib.sha256()
    for relative, body in files:
        encoded_path = relative.encode("utf-8")
        digest.update(len(encoded_path).to_bytes(8, "big"))
        digest.update(encoded_path)
        digest.update(len(body).to_bytes(8, "big"))
        digest.update(body)
    return digest.hexdigest()


def render_preloaded_skill_context(env: Mapping[str, str]) -> str | None:
    """Validate the deployed bundle and render every SKILL.md in stable order."""

    root_text = env.get(ENV_SKILLS_ROOT)
    if not root_text:
        return None
    expected_digest = env.get(ENV_SKILLS_SHA256, "")
    if len(expected_digest) != 64:
        raise RuntimeError(f"{ENV_SKILLS_SHA256} is missing or invalid")
    expected_skills = _positive_int(env, ENV_SKILL_COUNT)
    expected_files = _positive_int(env, ENV_BUNDLE_FILE_COUNT)

    files = _regular_bundle_files(Path(root_text))
    actual_digest = _bundle_digest(files)
    if actual_digest != expected_digest:
        raise RuntimeError(
            "deployed skill bundle digest mismatch: "
            f"expected {expected_digest}, got {actual_digest}"
        )
    if len(files) != expected_files:
        raise RuntimeError(
            f"deployed skill bundle file count mismatch: expected {expected_files}, "
            f"got {len(files)}"
        )

    skill_bodies: list[tuple[str, str]] = []
    for relative, body in files:
        if Path(relative).name != "SKILL.md":
            continue
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RuntimeError(f"SKILL.md must be valid UTF-8: {relative}") from exc
        skill_bodies.append((relative, text))
    if len(skill_bodies) != expected_skills:
        raise RuntimeError(
            f"deployed SKILL.md count mismatch: expected {expected_skills}, "
            f"got {len(skill_bodies)}"
        )

    sections = [
        PRELOAD_START,
        (
            "The benchmark executor deterministically preloaded the complete task "
            "skill bodies below before the original task prompt. They remain visible "
            "throughout this rollout and do not require invoke_skill to be read. "
            "Use them as the authoritative task procedures."
        ),
        f"bundle_sha256: sha256:{actual_digest}",
        f"skill_count: {len(skill_bodies)}",
    ]
    for relative, body in skill_bodies:
        sections.extend(
            [
                f'\n<SKILL_FILE path="{relative}">',
                body.rstrip("\n"),
                "</SKILL_FILE>",
            ]
        )
    sections.append(PRELOAD_END)
    return "\n".join(sections)


def _delegation_disabled(env: Mapping[str, str]) -> bool:
    raw = env.get(ENV_DISABLE_SUBAGENTS, "0")
    if raw not in {"0", "1"}:
        raise RuntimeError(f"{ENV_DISABLE_SUBAGENTS} must be '0' or '1', got {raw!r}")
    return raw == "1"


def _validated_agent_tools(agent: Any) -> list[Any]:
    tools = getattr(agent, "tools", None)
    if not isinstance(tools, list):
        raise RuntimeError("OpenHands Agent.tools must be a list")
    for tool in tools:
        name = getattr(tool, "name", None)
        if not isinstance(name, str) or not name:
            raise RuntimeError("OpenHands Agent contains a tool without a string name")
    return tools


def _assert_delegation_specs_disabled(agent: Any) -> None:
    leaked = sorted(
        {
            tool.name
            for tool in _validated_agent_tools(agent)
            if tool.name in DELEGATION_TOOL_SPEC_NAMES
        }
    )
    if leaked:
        raise RuntimeError(
            "OpenHands delegation tool specifications remain enabled after "
            "adapter filtering: " + ", ".join(leaked)
        )


def _assert_runtime_delegation_disabled(agent: Any) -> None:
    """Fail before an LLM request if lazy tool resolution leaked delegation."""

    tools_map = getattr(agent, "tools_map", None)
    if not isinstance(tools_map, Mapping):
        raise RuntimeError("OpenHands Agent.tools_map must be a mapping after init")
    runtime_names: set[str] = set()
    for key, tool in tools_map.items():
        name = getattr(tool, "name", None)
        if not isinstance(key, str) or not key:
            raise RuntimeError("OpenHands Agent.tools_map contains an invalid key")
        if not isinstance(name, str) or not name:
            raise RuntimeError(
                "OpenHands Agent.tools_map contains a tool without a string name"
            )
        runtime_names.update({key, name})
    leaked = sorted(runtime_names & DELEGATION_RUNTIME_TOOL_NAMES)
    if leaked:
        raise RuntimeError(
            "OpenHands delegation tools remain enabled after lazy resolution: "
            + ", ".join(leaked)
        )


def _without_delegation_tools(agent: Any) -> Any:
    tools = _validated_agent_tools(agent)
    filtered = [tool for tool in tools if tool.name not in DELEGATION_TOOL_SPEC_NAMES]
    configured = agent.model_copy(update={"tools": filtered})
    _assert_delegation_specs_disabled(configured)
    return configured


def configure_agent(agent: Any, env: Mapping[str, str]) -> Any:
    """Apply executor-owned tools and persistent AgentContext in memory."""

    configured = (
        _without_delegation_tools(agent) if _delegation_disabled(env) else agent
    )

    preloaded = render_preloaded_skill_context(env)
    if preloaded is None:
        return configured

    from openhands.sdk.context import AgentContext

    context = getattr(configured, "agent_context", None) or AgentContext()
    existing = (context.system_message_suffix or "").rstrip()
    merged = f"{existing}\n\n{preloaded}" if existing else preloaded
    updated_context = context.model_copy(update={"system_message_suffix": merged})
    return configured.model_copy(update={"agent_context": updated_context})


def _contains_iteration_limit(events: list[Any], start: int) -> bool:
    return any(
        getattr(event, "code", None) == "MaxIterationsReached"
        for event in events[start:]
    )


def _last_conversation_error_code(events: list[Any], start: int) -> str | None:
    codes = [
        code
        for event in events[start:]
        if isinstance((code := getattr(event, "code", None)), str)
    ]
    return codes[-1] if codes else None


def _execution_status(conversation: Any) -> str:
    raw = getattr(conversation.state, "execution_status", "")
    value = getattr(raw, "value", raw)
    return str(value).lower()


def _instrument_parent_iterations(agent: Any) -> None:
    """Count root-conversation ``agent.step`` calls without counting subagents."""

    agent_class = type(agent)
    if getattr(agent_class, "_benchmark_executor_step_instrumented", False):
        return
    original_step = agent_class.step

    @wraps(original_step)
    def counted_step(self: Any, conversation: Any, *args: Any, **kwargs: Any) -> Any:
        if (
            getattr(conversation, "_benchmark_executor_root", False)
            and getattr(conversation, "agent", None) is self
        ):
            used = getattr(conversation, "_benchmark_executor_total_iterations", 0)
            conversation._benchmark_executor_total_iterations = used + 1
        return original_step(self, conversation, *args, **kwargs)

    agent_class.step = counted_step
    agent_class._benchmark_executor_step_instrumented = True


def _instrument_runtime_delegation_guard(agent: Any) -> None:
    """Check lazy-resolved tools before OpenHands builds its system event."""

    agent_class = type(agent)
    if getattr(
        agent_class,
        "_benchmark_executor_delegation_guard_instrumented",
        False,
    ):
        return
    original_initialize = getattr(agent_class, "_initialize", None)
    if not callable(original_initialize):
        raise RuntimeError(
            "OpenHands Agent._initialize is unavailable; cannot verify delegation "
            "is disabled before the first provider request"
        )

    @wraps(original_initialize)
    def guarded_initialize(self: Any, *args: Any, **kwargs: Any) -> Any:
        result = original_initialize(self, *args, **kwargs)
        _assert_runtime_delegation_disabled(self)
        return result

    agent_class._initialize = guarded_initialize
    agent_class._benchmark_executor_delegation_guard_instrumented = True


def install_adapter(env: Mapping[str, str] | None = None) -> None:
    """Install idempotent in-memory hooks into the pinned OpenHands CLI."""

    global _PATCHED
    if _PATCHED:
        return
    runtime_env = os.environ if env is None else env
    max_iterations = _positive_int(runtime_env, ENV_MAX_ITERATIONS)

    from openhands_cli.acp_impl.agent import base_agent, local_agent

    original_conversation = local_agent.Conversation

    @wraps(original_conversation)
    def executor_conversation(*args: Any, **kwargs: Any) -> Any:
        if "agent" in kwargs:
            kwargs["agent"] = configure_agent(kwargs["agent"], runtime_env)
            configured_agent = kwargs["agent"]
        elif args:
            configured_agent = configure_agent(args[0], runtime_env)
            args = (configured_agent, *args[1:])
        else:
            raise RuntimeError("OpenHands Conversation was created without an agent")
        _instrument_parent_iterations(configured_agent)
        delegation_disabled = _delegation_disabled(runtime_env)
        if delegation_disabled:
            _assert_delegation_specs_disabled(configured_agent)
            _instrument_runtime_delegation_guard(configured_agent)
        kwargs["max_iteration_per_run"] = max_iterations
        conversation = original_conversation(*args, **kwargs)
        conversation._benchmark_executor_delegation_disabled = delegation_disabled
        conversation._benchmark_executor_root = True
        conversation._benchmark_executor_total_iterations = 0
        preloaded = bool(runtime_env.get(ENV_SKILLS_ROOT))
        conversation._benchmark_executor_skill_context_preloaded = preloaded
        conversation._benchmark_executor_skill_bundle_sha256 = (
            f"sha256:{runtime_env[ENV_SKILLS_SHA256]}" if preloaded else None
        )
        conversation._benchmark_executor_preloaded_skill_count = (
            _positive_int(runtime_env, ENV_SKILL_COUNT) if preloaded else 0
        )
        return conversation

    local_agent.Conversation = executor_conversation

    original_prompt = base_agent.BaseOpenHandsACPAgent.prompt

    @wraps(original_prompt)
    async def executor_prompt(
        self: Any, prompt: list[Any], session_id: str, **kwargs: Any
    ) -> Any:
        before = self.active_sessions.get(session_id)
        event_count = len(before.state.events) if before is not None else 0
        iterations_before = (
            getattr(before, "_benchmark_executor_total_iterations", 0)
            if before is not None
            else 0
        )
        result = await original_prompt(self, prompt, session_id, **kwargs)
        conversation = self.active_sessions.get(session_id)
        if conversation is None:
            return result
        events = list(conversation.state.events)
        iterations_after = getattr(
            conversation, "_benchmark_executor_total_iterations", iterations_before
        )
        iterations_used = iterations_after - iterations_before
        limit_reached = _contains_iteration_limit(events, event_count)
        if limit_reached and iterations_used != max_iterations:
            raise RuntimeError(
                "OpenHands reported MaxIterationsReached but the executor counted "
                f"{iterations_used}/{max_iterations} parent iterations"
            )
        stop_reason = "max_turn_requests" if limit_reached else result.stop_reason
        execution_status = _execution_status(conversation)
        error_code = _last_conversation_error_code(events, event_count)
        if limit_reached:
            semantic_stop_reason = "max_iterations"
        elif execution_status == "stuck":
            semantic_stop_reason = "stuck"
        elif error_code is not None or execution_status == "error":
            semantic_stop_reason = "conversation_error"
        elif execution_status == "paused":
            semantic_stop_reason = "paused"
        else:
            semantic_stop_reason = stop_reason
        field_meta = dict(getattr(result, "field_meta", None) or {})
        field_meta["benchmark_executor"] = {
            "stop_reason": semantic_stop_reason,
            "acp_stop_reason": stop_reason,
            "execution_status": execution_status or None,
            "error_code": error_code,
            "iterations_used": iterations_used,
            "max_iterations": max_iterations,
            "skill_context_preloaded": getattr(
                conversation,
                "_benchmark_executor_skill_context_preloaded",
                False,
            ),
            "skill_bundle_sha256": getattr(
                conversation, "_benchmark_executor_skill_bundle_sha256", None
            ),
            "preloaded_skill_count": getattr(
                conversation, "_benchmark_executor_preloaded_skill_count", 0
            ),
        }
        if hasattr(result, "model_copy"):
            return result.model_copy(
                update={"stop_reason": stop_reason, "field_meta": field_meta}
            )
        return base_agent.PromptResponse(
            stop_reason=stop_reason,
            _meta=field_meta,
        )

    base_agent.BaseOpenHandsACPAgent.prompt = executor_prompt
    _PATCHED = True


def main() -> None:
    """Install the adapter, then dispatch the normal OpenHands CLI arguments."""

    install_adapter()
    from openhands_cli.entrypoint import main as openhands_main

    openhands_main()


if __name__ == "__main__":
    main()
