"""Canonical policy for the shared SkillsBench rollout executor.

Diagnosis, repair, and refinement algorithms live outside this package.  This
module owns the invariants that must be identical whenever one of those
algorithms asks BenchFlow to execute an actual task rollout.
"""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from benchflow.skill_policy import TaskSkillPolicy

EXECUTOR_AGENT = "openhands"
EXECUTOR_PROTOCOL_ID = "skillrepair-v1"
EXECUTOR_PROTOCOL_VERSION = 1
EXECUTOR_SANDBOX = "docker"
EXECUTOR_USAGE_TRACKING = "auto"
EXECUTOR_MAX_ROLLOUT_RETRIES = 0
EXECUTOR_SKILL_EXPOSURE_MODE = "persistent-agent-context-full-skill-md"
BENCHFLOW_BASE_VERSION = "v0.6.7"
BENCHFLOW_BASE_COMMIT = "aadad44acf27f193df98f438443116d514f51fb8"
OPENHANDS_CLI_COMMIT = "2df8a2835d3f1bd2f2eadf5a7a2e1ad0dfb0d271"
OPENHANDS_SDK_VERSION = "1.28.1"
OPENHANDS_TOOLS_VERSION = "1.28.1"
MAX_PARENT_ITERATIONS_PER_STEP = 60

# These are hang watchdogs, not evaluation budgets.  The scored budget is the
# parent-agent iteration cap above.  A pending tool call is already exempt from
# the idle watchdog by the ACP runtime and is covered by the high wall backstop.
WALL_CLOCK_SAFETY_TIMEOUT_SEC = 21_600
IDLE_SAFETY_TIMEOUT_SEC = 3_600
LLM_REQUEST_SAFETY_TIMEOUT_SEC = 3_600

ENV_MAX_ITERATIONS = "BENCHMARK_EXECUTOR_MAX_ITERATIONS"
ENV_SKILLS_ROOT = "BENCHMARK_EXECUTOR_SKILLS_ROOT"
ENV_SKILLS_SHA256 = "BENCHMARK_EXECUTOR_SKILLS_SHA256"
ENV_SKILL_COUNT = "BENCHMARK_EXECUTOR_SKILL_COUNT"
ENV_BUNDLE_FILE_COUNT = "BENCHMARK_EXECUTOR_BUNDLE_FILE_COUNT"
ENV_LLM_TIMEOUT = "LLM_TIMEOUT"
ENV_DISABLE_SUBAGENTS = "BENCHFLOW_OPENHANDS_DISABLE_SUBAGENTS"

_RESERVED_ENV = frozenset(
    {
        ENV_MAX_ITERATIONS,
        ENV_SKILLS_ROOT,
        ENV_SKILLS_SHA256,
        ENV_SKILL_COUNT,
        ENV_BUNDLE_FILE_COUNT,
        ENV_LLM_TIMEOUT,
        ENV_DISABLE_SUBAGENTS,
    }
)

# These generic overrides can make a provider-qualified model route execute
# against a different endpoint/model while preserving the original label.
# Provider-specific configuration (for example DEEPSEEK_BASE_URL or a vllm/
# endpoint) remains supported through the provider registry and is recorded.
_PROVIDER_ROUTE_OVERRIDE_ENV = frozenset(
    {
        "BENCHFLOW_PROVIDER_BASE_URL",
        "BENCHFLOW_PROVIDER_MODEL",
        "BENCHFLOW_PROVIDER_NAME",
        "BENCHFLOW_PROVIDER_PROTOCOL",
        "LLM_BASE_URL",
        "LLM_MODEL",
    }
)


@dataclass(frozen=True)
class SkillBundleManifest:
    """Deterministic identity for the complete deployed skill bundle."""

    sha256: str
    skill_files: tuple[str, ...]
    file_count: int
    total_bytes: int

    @property
    def skill_count(self) -> int:
        return len(self.skill_files)

    def to_metadata(self) -> dict[str, Any]:
        return {
            "skill_bundle_sha256": f"sha256:{self.sha256}",
            "preloaded_skill_count": self.skill_count,
            "preloaded_skill_files": list(self.skill_files),
            "skill_bundle_file_count": self.file_count,
            "skill_bundle_bytes": self.total_bytes,
        }


def _regular_bundle_files(root: Path) -> list[tuple[str, bytes]]:
    """Read every regular bundle file with stable paths and no symlink escape."""

    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"skill bundle root is not a directory: {root}")

    files: list[tuple[str, bytes]] = []
    for path in sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix()):
        relative = path.relative_to(root)
        if path.is_symlink() or any(
            (root / parent).is_symlink() for parent in relative.parents if parent.parts
        ):
            raise ValueError(f"skill bundle cannot contain symlinks: {relative}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError(f"skill bundle contains a non-regular file: {relative}")
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise ValueError(f"skill bundle file escapes its root: {relative}")
        files.append((relative.as_posix(), path.read_bytes()))
    return files


def _bundle_digest(files: list[tuple[str, bytes]]) -> str:
    """Hash unambiguous length-delimited ``(relative path, bytes)`` records."""

    digest = hashlib.sha256()
    for relative, body in files:
        encoded_path = relative.encode("utf-8")
        digest.update(len(encoded_path).to_bytes(8, "big"))
        digest.update(encoded_path)
        digest.update(len(body).to_bytes(8, "big"))
        digest.update(body)
    return digest.hexdigest()


def build_skill_bundle_manifest(root: Path) -> SkillBundleManifest:
    """Validate and fingerprint a full skill bundle.

    A bundle must contain at least one UTF-8 ``SKILL.md``.  All files are part
    of the bundle digest, while only the complete ``SKILL.md`` bodies are
    preloaded into OpenHands' persistent AgentContext.
    """

    files = _regular_bundle_files(root)
    if not files:
        raise ValueError(f"skill bundle is empty: {root}")
    skill_files = tuple(path for path, _ in files if Path(path).name == "SKILL.md")
    if not skill_files:
        raise ValueError(f"skill bundle contains no SKILL.md: {root}")
    bodies = dict(files)
    for relative in skill_files:
        try:
            bodies[relative].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"SKILL.md must be valid UTF-8: {relative}") from exc
    return SkillBundleManifest(
        sha256=_bundle_digest(files),
        skill_files=skill_files,
        file_count=len(files),
        total_bytes=sum(len(body) for _, body in files),
    )


def snapshot_skill_bundle(source: Path, destination: Path) -> SkillBundleManifest:
    """Freeze ``source`` into the rollout inputs and return its verified digest."""

    source_manifest = build_skill_bundle_manifest(source)
    if destination.exists():
        raise FileExistsError(f"skill bundle snapshot already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, symlinks=False)
    snapshot_manifest = build_skill_bundle_manifest(destination)
    if snapshot_manifest != source_manifest:
        raise RuntimeError(
            "skill bundle changed while its rollout snapshot was created"
        )
    return snapshot_manifest


def apply_openhands_executor_env(
    agent: str,
    agent_env: dict[str, str],
    *,
    skill_policy: TaskSkillPolicy | None,
    manifest: SkillBundleManifest | None,
) -> dict[str, str]:
    """Return a scrubbed env containing only executor-owned adapter controls."""

    result = {
        key: value for key, value in agent_env.items() if key not in _RESERVED_ENV
    }
    if agent != EXECUTOR_AGENT:
        return result

    result[ENV_MAX_ITERATIONS] = str(MAX_PARENT_ITERATIONS_PER_STEP)
    result[ENV_LLM_TIMEOUT] = str(LLM_REQUEST_SAFETY_TIMEOUT_SEC)
    result[ENV_DISABLE_SUBAGENTS] = "1"
    if skill_policy is None or not skill_policy.enabled:
        return result
    if manifest is None or skill_policy.sandbox_dir is None:
        raise RuntimeError(
            "enabled OpenHands skills require a verified bundle manifest"
        )
    result.update(
        {
            ENV_SKILLS_ROOT: skill_policy.sandbox_dir,
            ENV_SKILLS_SHA256: manifest.sha256,
            ENV_SKILL_COUNT: str(manifest.skill_count),
            ENV_BUNDLE_FILE_COUNT: str(manifest.file_count),
        }
    )
    return result


def provider_route_for_model(model: str) -> str:
    """Return the registered provider selected by a qualified model route."""

    from benchflow.agents.providers import find_provider

    selected = find_provider(model.strip())
    if selected is None:
        raise ValueError(
            "benchmark-executor requires a registered provider-qualified model "
            "route such as 'openrouter/openai/model' or 'openai/model'; "
            f"got {model!r}"
        )
    return selected[0]


def validate_openhands_executor_model(agent: str, model: str | None) -> None:
    """Require a provider-qualified route without binding to one provider/model."""

    if agent == EXECUTOR_AGENT and (not isinstance(model, str) or not model.strip()):
        raise ValueError(
            "benchmark-executor OpenHands rollouts require an explicit model route"
        )
    if agent == EXECUTOR_AGENT:
        assert isinstance(model, str)
        provider_route_for_model(model)


def validate_openhands_executor_agent_env(
    agent: str, agent_env: dict[str, str] | None
) -> None:
    """Reject generic endpoint/model overrides that falsify route provenance."""

    if agent != EXECUTOR_AGENT:
        return
    forbidden = sorted(_PROVIDER_ROUTE_OVERRIDE_ENV.intersection(agent_env or {}))
    if forbidden:
        raise ValueError(
            "benchmark-executor provider/model selection must come from the "
            "qualified model route, not agent_env overrides; remove: "
            + ", ".join(forbidden)
        )


def validate_method_skill_task_count(
    skills_dir: str | Path | None, task_count: int
) -> None:
    """A custom full bundle is task-specific and may target exactly one task."""

    if skills_dir is not None and task_count != 1:
        raise ValueError(
            "benchmark-executor method-skill runs require exactly one selected "
            f"task per command, got {task_count}"
        )


def validate_openhands_executor_scenes(
    scenes: list[Any],
    *,
    expected_model: str | None = None,
    expected_reasoning_effort: str | None = None,
) -> None:
    """Reject Scene features that bypass one selected execution policy."""

    for scene in scenes:
        if getattr(scene, "skills_dir", None) is not None:
            raise ValueError(
                "benchmark-executor does not allow Scene-local skills_dir; submit "
                "one complete bundle through the evaluation --skills-dir option"
            )
        for role in getattr(scene, "roles", ()):
            if getattr(role, "agent", None) != EXECUTOR_AGENT:
                raise ValueError(
                    "canonical OpenHands rollouts require every Scene role to use "
                    f"agent {EXECUTOR_AGENT!r}"
                )
            validate_openhands_executor_model(role.agent, role.model)
            if expected_model is not None and role.model != expected_model:
                raise ValueError(
                    "all canonical OpenHands Scene roles must use the model route "
                    f"selected for this rollout ({expected_model!r}), got "
                    f"{role.model!r}"
                )
            if getattr(role, "reasoning_effort", None) != expected_reasoning_effort:
                raise ValueError(
                    "all canonical OpenHands Scene roles must use the reasoning "
                    "effort selected for this rollout "
                    f"({expected_reasoning_effort!r}), got "
                    f"{getattr(role, 'reasoning_effort', None)!r}"
                )
            if getattr(role, "env", None):
                raise ValueError(
                    "benchmark-executor does not allow Role-local env overrides; "
                    "select the provider/model once for the rollout"
                )
            if getattr(role, "skills_dir", None) is not None:
                raise ValueError(
                    "benchmark-executor does not allow Role-local skills_dir; submit "
                    "one complete bundle through the evaluation --skills-dir option"
                )


def evaluation_condition(skill_policy: TaskSkillPolicy) -> str:
    """Name the comparable benchmark condition represented by a skill policy."""

    from benchflow.skill_policy import (
        SKILL_SOURCE_CUSTOM_RUNTIME,
        SKILL_SOURCE_TASK_BUNDLED,
    )

    if not skill_policy.enabled:
        return "no-skill"
    if skill_policy.source == SKILL_SOURCE_TASK_BUNDLED:
        return "original-skill"
    if skill_policy.source == SKILL_SOURCE_CUSTOM_RUNTIME:
        return "method-skill"
    return skill_policy.source.replace("_", "-")


def executor_metadata(
    *,
    agent: str,
    model: str | None,
    skill_policy: TaskSkillPolicy,
    manifest: SkillBundleManifest | None,
    resolved_agent_env: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """Build auditable config/result metadata for canonical OpenHands runs."""

    if agent != EXECUTOR_AGENT:
        return None
    validate_openhands_executor_model(agent, model)
    assert isinstance(model, str)
    provider_route = provider_route_for_model(model)
    resolved_provider = (resolved_agent_env or {}).get("BENCHFLOW_PROVIDER_NAME")
    if resolved_provider is not None and resolved_provider != provider_route:
        raise RuntimeError(
            "resolved provider does not match the selected model route: "
            f"{resolved_provider!r} != {provider_route!r}"
        )
    data: dict[str, Any] = {
        "name": "benchmark-executor",
        "protocol_id": EXECUTOR_PROTOCOL_ID,
        "protocol_version": EXECUTOR_PROTOCOL_VERSION,
        "benchflow_base_version": BENCHFLOW_BASE_VERSION,
        "benchflow_base_commit": BENCHFLOW_BASE_COMMIT,
        "openhands_cli_commit": OPENHANDS_CLI_COMMIT,
        "openhands_sdk_version": OPENHANDS_SDK_VERSION,
        "openhands_tools_version": OPENHANDS_TOOLS_VERSION,
        "agent": EXECUTOR_AGENT,
        "model": model,
        "provider_route": provider_route,
        "provider_base_url": (resolved_agent_env or {}).get(
            "BENCHFLOW_PROVIDER_BASE_URL"
        ),
        "provider_protocol": (resolved_agent_env or {}).get(
            "BENCHFLOW_PROVIDER_PROTOCOL"
        ),
        "skill_exposure_mode": EXECUTOR_SKILL_EXPOSURE_MODE,
        "evaluation_condition": evaluation_condition(skill_policy),
        "max_parent_iterations_per_step": MAX_PARENT_ITERATIONS_PER_STEP,
        "iteration_scope": "one OpenHands Conversation.run per BenchFlow execution Step",
        "wall_clock_is_safety_watchdog": True,
        "wall_clock_safety_timeout_sec": WALL_CLOCK_SAFETY_TIMEOUT_SEC,
        "idle_safety_timeout_sec": IDLE_SAFETY_TIMEOUT_SEC,
        "llm_request_safety_timeout_sec": LLM_REQUEST_SAFETY_TIMEOUT_SEC,
        "delegation_disabled": True,
        "skill_context_preloaded": bool(skill_policy.enabled),
    }
    if manifest is not None:
        data.update(manifest.to_metadata())
    return data


def protocol_descriptor() -> dict[str, Any]:
    """Return the immutable public protocol contract for automated callers."""

    return {
        "name": "benchmark-executor",
        "protocol_id": EXECUTOR_PROTOCOL_ID,
        "protocol_version": EXECUTOR_PROTOCOL_VERSION,
        "base_repository": "https://github.com/benchflow-ai/benchflow.git",
        "base_version": BENCHFLOW_BASE_VERSION,
        "base_commit": BENCHFLOW_BASE_COMMIT,
        "openhands_cli_commit": OPENHANDS_CLI_COMMIT,
        "openhands_sdk_version": OPENHANDS_SDK_VERSION,
        "openhands_tools_version": OPENHANDS_TOOLS_VERSION,
        "agent": EXECUTOR_AGENT,
        "model_policy": "selected once per executor instance and recorded per rollout",
        "provider_policy": (
            "registered provider-qualified model route; generic endpoint/model "
            "overrides rejected"
        ),
        "reasoning_effort_policy": "selected once per executor instance and recorded per rollout",
        "sandbox": EXECUTOR_SANDBOX,
        "container_host_gateway": (
            "host.docker.internal with Linux host-gateway mapping"
        ),
        "provider_proxy_port": "dynamic per rollout",
        "provider_proxy_preflight": (
            "task-container health probe before first provider request"
        ),
        "usage_tracking": EXECUTOR_USAGE_TRACKING,
        "max_rollout_retries_per_call": EXECUTOR_MAX_ROLLOUT_RETRIES,
        "max_parent_iterations_per_step": MAX_PARENT_ITERATIONS_PER_STEP,
        "skill_exposure_mode": EXECUTOR_SKILL_EXPOSURE_MODE,
        "delegation_disabled": True,
        "wall_clock_safety_timeout_sec": WALL_CLOCK_SAFETY_TIMEOUT_SEC,
        "idle_safety_timeout_sec": IDLE_SAFETY_TIMEOUT_SEC,
        "llm_request_safety_timeout_sec": LLM_REQUEST_SAFETY_TIMEOUT_SEC,
        "evaluation_conditions": ["no-skill", "original-skill", "method-skill"],
        "verifier_dependency_install_policy": (
            "fail closed before reward parsing; classify as non-comparable"
        ),
        "task_identity": "live task digest recorded per rollout",
    }


def executor_result_metadata(
    metadata: dict[str, Any] | None,
    trajectory: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Add observed iteration-limit evidence without treating it as infra error."""

    if metadata is None:
        return None
    result = dict(metadata)
    outcomes = [
        event for event in trajectory if event.get("type") == "agent_iteration_outcome"
    ]
    prompt_count = sum(1 for event in trajectory if event.get("type") == "user_message")
    result["iteration_accounting_complete"] = len(outcomes) == prompt_count
    hits = [event for event in outcomes if event.get("stop_reason") == "max_iterations"]
    result["iteration_limit_reached"] = bool(hits)
    result["iteration_limit_hits"] = len(hits)
    result["stop_reason"] = outcomes[-1].get("stop_reason") if outcomes else None
    if not outcomes and not hits:
        timeout_events = [
            event for event in trajectory if event.get("type") == "agent_timeout"
        ]
        if timeout_events:
            result["stop_reason"] = timeout_events[-1].get("reason")
    prompt_events = outcomes
    result["prompt_runs"] = [
        {
            "prompt_ordinal": event.get("prompt_ordinal"),
            "stop_reason": event.get("stop_reason", "max_iterations"),
            "acp_stop_reason": event.get("acp_stop_reason", "max_turn_requests"),
            "execution_status": event.get("execution_status"),
            "error_code": event.get("error_code"),
            "iterations_used": event.get("iterations_used"),
            "max_iterations": event.get("max_iterations"),
            "skill_context_preloaded": event.get("skill_context_preloaded"),
            "skill_bundle_sha256": event.get("skill_bundle_sha256"),
            "preloaded_skill_count": event.get("preloaded_skill_count"),
        }
        for event in prompt_events
    ]
    if outcomes:
        observed = outcomes[-1].get("skill_context_preloaded")
        result["skill_context_preload_observed"] = observed
        result["observed_skill_bundle_sha256"] = outcomes[-1].get("skill_bundle_sha256")
        result["observed_preloaded_skill_count"] = outcomes[-1].get(
            "preloaded_skill_count"
        )
        result["skill_context_preload_matches_expected"] = observed == result.get(
            "skill_context_preloaded"
        )
    else:
        result["skill_context_preload_observed"] = None
        result["observed_skill_bundle_sha256"] = None
        result["observed_preloaded_skill_count"] = None
        result["skill_context_preload_matches_expected"] = None
    return result


def executor_wall_clock_timeout(agent: str, fallback: int) -> int:
    """Use a high hang backstop for canonical OpenHands rollouts."""

    return WALL_CLOCK_SAFETY_TIMEOUT_SEC if agent == EXECUTOR_AGENT else fallback


def executor_idle_timeout(agent: str, fallback: int | None) -> int | None:
    """Use a high inactivity backstop for canonical OpenHands rollouts."""

    return IDLE_SAFETY_TIMEOUT_SEC if agent == EXECUTOR_AGENT else fallback


__all__ = [
    "EXECUTOR_AGENT",
    "EXECUTOR_MAX_ROLLOUT_RETRIES",
    "EXECUTOR_PROTOCOL_ID",
    "EXECUTOR_PROTOCOL_VERSION",
    "EXECUTOR_SANDBOX",
    "EXECUTOR_SKILL_EXPOSURE_MODE",
    "EXECUTOR_USAGE_TRACKING",
    "ENV_DISABLE_SUBAGENTS",
    "IDLE_SAFETY_TIMEOUT_SEC",
    "LLM_REQUEST_SAFETY_TIMEOUT_SEC",
    "MAX_PARENT_ITERATIONS_PER_STEP",
    "SkillBundleManifest",
    "WALL_CLOCK_SAFETY_TIMEOUT_SEC",
    "apply_openhands_executor_env",
    "build_skill_bundle_manifest",
    "evaluation_condition",
    "executor_idle_timeout",
    "executor_metadata",
    "executor_result_metadata",
    "executor_wall_clock_timeout",
    "protocol_descriptor",
    "provider_route_for_model",
    "snapshot_skill_bundle",
    "validate_method_skill_task_count",
    "validate_openhands_executor_model",
    "validate_openhands_executor_agent_env",
    "validate_openhands_executor_scenes",
]
