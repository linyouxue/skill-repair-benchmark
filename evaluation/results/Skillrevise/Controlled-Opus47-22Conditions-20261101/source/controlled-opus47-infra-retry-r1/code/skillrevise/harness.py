"""Docker-backed DeepSeek executor for real SkillsBench episodes.

Run this module through ``--harness-command "python -m skillrevise.harness"``.
``CommandAgentHarness`` supplies the task workspace, instruction, optional Skill
path, and trace destination through environment variables.  This module builds
the task image, lets an OpenAI-compatible tool-calling model operate a shell
inside that image, runs the task verifier in the container, and writes the
trace format expected by SkillRevise.

The executor is intentionally configured separately from the LLM used to
author, diagnose, and revise skills.  See ``ExecutorConfig`` for variables.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4


DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-flash"
# A handoff task can require inspecting several input/codebook files, writing a
# solver, and validating its output.  Keep a finite guardrail while allowing
# that complete workflow under the documented fixed experiment condition.
DEFAULT_MAX_TOOL_CALLS = 64
DEFAULT_MODEL_TIMEOUT_SECONDS = 120
DEFAULT_COMMAND_TIMEOUT_SECONDS = 120
DEFAULT_MAX_TOKENS = 4_096
MAX_TOOL_OUTPUT_CHARS = 8_000


class HarnessError(RuntimeError):
    """Raised when the local Docker executor cannot complete an episode."""


@dataclass(frozen=True)
class ExecutorConfig:
    """Configuration for the task-executing agent, not the revision LLM."""

    api_key: str
    base_url: str
    model: str
    max_tool_calls: int
    model_timeout_seconds: int
    command_timeout_seconds: int
    max_tokens: int
    temperature: float
    seed: int | None
    reasoning_effort: str | None


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


def main() -> None:
    """Run one harness episode and return verifier status as the process code."""

    started = time.monotonic()
    started_at = _utc_now()
    trace_path = Path(os.environ.get("SKILL_REVISE_TRACE_PATH", "harness_trace.json"))
    task_id = os.environ.get("SKILL_REVISE_TASK_ID", "unknown-task")
    events: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {"harness": "docker-deepseek"}
    tokens = 0
    tool_calls = 0
    outcome_summary = "Harness did not run."
    exit_code = 2
    container_id: str | None = None
    image_tag: str | None = None
    remove_image_after_run = False

    try:
        config = load_executor_config(os.environ)
        workspace = _required_path("SKILL_REVISE_WORKSPACE")
        instruction = _required_text("SKILL_REVISE_INSTRUCTION")
        skill_text = _read_optional_skill(os.environ.get("SKILL_REVISE_SKILL_PATH", ""))
        if skill_text is not None:
            skill_sha256 = hashlib.sha256(skill_text.encode("utf-8")).hexdigest()
            metadata["skill_context"] = {"sha256": skill_sha256, "characters": len(skill_text)}
            events.append(
                _event(
                    len(events) + 1,
                    "skill_context",
                    "Injected the supplied initial Skill into the execution agent's task context.",
                    f"SHA-256: {skill_sha256}",
                    {"sha256": skill_sha256, "characters": len(skill_text)},
                )
            )
        image_tag, remove_image_after_run = _build_task_image(
            workspace,
            task_id,
            config.command_timeout_seconds,
        )
        container_id, working_directory = _start_container(
            image_tag,
            workspace,
            config.command_timeout_seconds,
        )
        _copy_verifier_files(container_id, workspace, config.command_timeout_seconds)

        agent = DockerToolAgent(
            config=config,
            container_id=container_id,
            working_directory=working_directory,
        )
        agent_result = agent.solve(
            instruction=instruction,
            skill_text=skill_text,
        )
        events.extend(agent_result["events"])
        tokens = agent_result["tokens"]
        tool_calls = agent_result["tool_calls"]
        metadata.update(
            {
                "image_tag": image_tag,
                "agent_final": agent_result["final"],
                "executor_config": {
                    "base_url": config.base_url,
                    "model": config.model,
                    "max_tool_calls": config.max_tool_calls,
                    "http_timeout_seconds": config.model_timeout_seconds,
                    "command_timeout_seconds": config.command_timeout_seconds,
                    "max_tokens": config.max_tokens,
                    "temperature": config.temperature,
                    "seed": config.seed,
                },
            }
        )

        verifier = _run_verifier(container_id, config.command_timeout_seconds)
        reward = _read_reward(container_id, config.command_timeout_seconds)
        success = verifier.returncode == 0 and reward >= 1.0
        exit_code = 0 if success else 1
        outcome_summary = _summarize_verifier(verifier, reward)
        events.append(
            _event(
                len(events) + 1,
                "verifier",
                outcome_summary,
                _tail(verifier.stdout + "\n" + verifier.stderr),
                {"exit_code": verifier.returncode, "reward": reward},
            )
        )
        metadata["reward"] = reward
        metadata["verifier_exit_code"] = verifier.returncode
    except Exception as exc:  # Always give the parent adapter a trace to diagnose.
        outcome_summary = f"Harness error: {exc}"
        metadata["reward"] = 0.0
        metadata["harness_error"] = str(exc)
        events.append(_event(len(events) + 1, "harness_error", outcome_summary, ""))
        exit_code = 2
    finally:
        if container_id:
            _remove_container(container_id)
        if image_tag and remove_image_after_run:
            _remove_image(image_tag)
        payload = {
            "tokens": tokens,
            "tool_calls": tool_calls,
            "steps": len(events),
            "latency_seconds": round(time.monotonic() - started, 4),
            "outcome_summary": outcome_summary,
            "events": events,
            "metadata": metadata | {"started_at": started_at, "ended_at": _utc_now()},
        }
        _write_trace(trace_path, payload)

    raise SystemExit(exit_code)


class DockerToolAgent:
    """A small OpenAI-compatible tool-calling loop backed by ``docker exec``."""

    def __init__(
        self,
        *,
        config: ExecutorConfig,
        container_id: str,
        working_directory: str,
        system_prompt: str | None = None,
    ) -> None:
        self.config = config
        self.container_id = container_id
        self.working_directory = working_directory or "/"
        self.system_prompt = system_prompt or _agent_system_prompt()

    def solve(self, *, instruction: str, skill_text: str | None) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": _agent_task_prompt(
                    instruction=instruction,
                    skill_text=skill_text,
                    working_directory=self.working_directory,
                ),
            },
        ]
        events: list[dict[str, Any]] = []
        total_tokens = 0
        tool_calls = 0
        final_text = ""

        for _ in range(self.config.max_tool_calls + 1):
            response = _chat_completion(self.config, messages, _shell_tool_schema())
            total_tokens += _usage_total_tokens(response.get("usage"))
            choice = _first_choice(response)
            message = choice.get("message") or {}
            if not isinstance(message, dict):
                raise HarnessError("Executor response did not contain a message object.")

            content = str(message.get("content") or "").strip()
            raw_calls = message.get("tool_calls") or []
            messages.append(
                {
                    "role": "assistant",
                    "content": content or None,
                    "tool_calls": raw_calls,
                }
            )
            if not raw_calls:
                final_text = content or "Agent ended without a textual final response."
                break

            for raw_call in raw_calls:
                tool_calls += 1
                command = _tool_command(raw_call)
                result = self._run_shell(command)
                summary = f"shell: {command[:240]}"
                evidence = _tail(result.stdout + "\n" + result.stderr)
                events.append(
                    _event(
                        len(events) + 1,
                        "tool",
                        summary,
                        evidence,
                        {"exit_code": result.returncode},
                    )
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(raw_call.get("id", "shell-call")),
                        "content": json.dumps(
                            {
                                "exit_code": result.returncode,
                                "stdout": _tail(result.stdout),
                                "stderr": _tail(result.stderr),
                            },
                            ensure_ascii=False,
                        ),
                    }
                )
                if tool_calls >= self.config.max_tool_calls:
                    final_text = f"Stopped after configured limit of {self.config.max_tool_calls} shell calls."
                    break
            if tool_calls >= self.config.max_tool_calls:
                break
        else:
            final_text = "Agent exceeded its interaction limit."

        return {
            "events": events,
            "tokens": total_tokens,
            "tool_calls": tool_calls,
            "final": final_text,
        }

    def _run_shell(self, command: str) -> CommandResult:
        return _run_command(
            [
                "docker",
                "exec",
                "-i",
                "--workdir",
                self.working_directory,
                self.container_id,
                "/bin/sh",
                "-lc",
                command,
            ],
            timeout_seconds=self.config.command_timeout_seconds,
        )


def load_executor_config(env: Mapping[str, str]) -> ExecutorConfig:
    """Load executor settings and fail clearly instead of falling back to mocks."""

    api_key = (env.get("SKILL_REVISE_EXECUTOR_API_KEY") or "").strip()
    if not api_key:
        raise HarnessError("Missing SKILL_REVISE_EXECUTOR_API_KEY.")
    return ExecutorConfig(
        api_key=api_key,
        base_url=(env.get("SKILL_REVISE_EXECUTOR_BASE_URL") or DEFAULT_BASE_URL).strip().rstrip("/"),
        model=(env.get("SKILL_REVISE_EXECUTOR_MODEL") or DEFAULT_MODEL).strip(),
        max_tool_calls=_positive_int(env, "SKILL_REVISE_EXECUTOR_MAX_TOOL_CALLS", DEFAULT_MAX_TOOL_CALLS),
        model_timeout_seconds=_positive_int(
            env,
            "SKILL_REVISE_EXECUTOR_HTTP_TIMEOUT",
            DEFAULT_MODEL_TIMEOUT_SECONDS,
        ),
        command_timeout_seconds=_positive_int(
            env,
            "SKILL_REVISE_EXECUTOR_COMMAND_TIMEOUT",
            DEFAULT_COMMAND_TIMEOUT_SECONDS,
        ),
        max_tokens=_positive_int(env, "SKILL_REVISE_EXECUTOR_MAX_TOKENS", DEFAULT_MAX_TOKENS),
        temperature=_float(env, "SKILL_REVISE_EXECUTOR_TEMPERATURE", 0.2),
        seed=_optional_int(env, "SKILL_REVISE_EXECUTOR_SEED"),
        reasoning_effort=_optional_reasoning_effort(env, "SKILL_REVISE_EXECUTOR_REASONING_EFFORT"),
    )


def _build_task_image(workspace: Path, task_id: str, timeout_seconds: int) -> tuple[str, bool]:
    context = workspace / "environment"
    dockerfile = context / "Dockerfile"
    if not dockerfile.is_file():
        raise HarnessError(f"Task workspace has no environment/Dockerfile: {dockerfile}")
    cache_images = _task_image_cache_enabled(os.environ)
    tag = _cached_task_image_tag(context, task_id) if cache_images else f"skillrevise-{_safe_name(task_id)}-{uuid4().hex[:10]}"
    if cache_images and _docker_image_exists(tag, timeout_seconds):
        return tag, False
    retrying_dockerfile = _dockerfile_with_apt_retries(
        dockerfile,
        apt_mirror=_apt_mirror_url(os.environ),
        debian_apt_mirror=_debian_apt_mirror_url(os.environ),
    )
    try:
        result = _run_command(
            [
                "docker",
                "build",
                *_docker_build_proxy_args(os.environ),
                "--file",
                str(retrying_dockerfile),
                "--tag",
                tag,
                str(context),
            ],
            timeout_seconds=max(timeout_seconds, 600),
        )
    finally:
        if retrying_dockerfile != dockerfile:
            retrying_dockerfile.unlink(missing_ok=True)
    if result.returncode != 0:
        # BuildKit can finish exporting an image while its CLI client is being
        # terminated by the local timeout.  In that case the image is usable;
        # treating it as a failure would force an unnecessary rebuild.
        if _docker_image_exists(tag, 30):
            return tag, not cache_images
        raise HarnessError(f"Docker build failed: {_tail(result.stderr or result.stdout)}")
    return tag, not cache_images


def _task_image_cache_enabled(env: Mapping[str, str]) -> bool:
    value = (env.get("SKILL_REVISE_CACHE_TASK_IMAGES") or "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _cached_task_image_tag(context: Path, task_id: str) -> str:
    digest = hashlib.sha256()
    for path in sorted((item for item in context.rglob("*") if item.is_file()), key=lambda item: item.as_posix()):
        if path.name == ".skillrevise-retry.Dockerfile":
            continue
        digest.update(path.relative_to(context).as_posix().encode("utf-8"))
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1_048_576), b""):
                digest.update(chunk)
    return f"skillrevise-{_safe_name(task_id)}-{digest.hexdigest()[:16]}"


def _docker_image_exists(tag: str, timeout_seconds: int) -> bool:
    result = _run_command(
        ["docker", "image", "inspect", tag],
        timeout_seconds=max(30, timeout_seconds),
    )
    return result.returncode == 0


def _docker_build_proxy_args(env: Mapping[str, str]) -> list[str]:
    """Pass an explicitly configured Windows-host proxy into Docker builds."""

    proxy = (env.get("SKILL_REVISE_DOCKER_PROXY") or "").strip()
    if not proxy:
        return []
    return [
        "--build-arg",
        f"HTTP_PROXY={proxy}",
        "--build-arg",
        f"HTTPS_PROXY={proxy}",
        "--build-arg",
        f"http_proxy={proxy}",
        "--build-arg",
        f"https_proxy={proxy}",
    ]


def _apt_mirror_url(env: Mapping[str, str]) -> str | None:
    """Return an optional base URL for Ubuntu APT repositories."""

    return _mirror_url(env, "SKILL_REVISE_APT_MIRROR")


def _debian_apt_mirror_url(env: Mapping[str, str]) -> str | None:
    """Return an optional base URL for Debian APT repositories."""

    return _mirror_url(env, "SKILL_REVISE_DEBIAN_APT_MIRROR")


def _mirror_url(env: Mapping[str, str], key: str) -> str | None:
    value = (env.get(key) or "").strip().rstrip("/")
    if not value:
        return None
    if not re.fullmatch(r"https?://[A-Za-z0-9._~:/-]+", value):
        raise HarnessError(f"{key} must be an http(s) mirror base URL.")
    return value


def _dockerfile_with_apt_retries(
    dockerfile: Path,
    *,
    apt_mirror: str | None = None,
    debian_apt_mirror: str | None = None,
) -> Path:
    """Create a temporary Dockerfile that retries complete apt install steps.

    SkillsBench bundles intentionally bring their own environments.  This only
    adds retry controls and leaves task commands, packages, and files unchanged.
    Re-running the complete instruction matters because apt can exhaust its
    per-download retries when a large dependency set gets a transient 502.
    """

    source = dockerfile.read_text(encoding="utf-8")
    marker = "# skillrevise: apt network retries"
    if marker in source and not apt_mirror and not debian_apt_mirror:
        return dockerfile
    retry_layer = (
        f"{marker}\n"
        "RUN if [ -d /etc/apt/apt.conf.d ]; then "
        "echo 'Acquire::Retries \"5\";' > /etc/apt/apt.conf.d/99skillrevise-retries; "
        "rm -f /etc/apt/apt.conf.d/docker-clean; fi\n"
    )
    mirror_layer = ""
    if apt_mirror:
        mirror_layer = (
            "# skillrevise: apt mirror\n"
            "RUN if [ -d /etc/apt ]; then find /etc/apt -type f "
            "\\( -name '*.list' -o -name '*.sources' \\) -exec sed -i "
            f"-e 's|http://archive.ubuntu.com/ubuntu|{apt_mirror}|g' "
            f"-e 's|http://security.ubuntu.com/ubuntu|{apt_mirror}|g' {{}} +; fi\n"
        )
    if debian_apt_mirror:
        mirror_layer += (
            "# skillrevise: Debian apt mirror\n"
            "RUN if [ -d /etc/apt ]; then find /etc/apt -type f "
            "\\( -name '*.list' -o -name '*.sources' \\) -exec sed -i "
            f"-e 's|http://deb.debian.org/debian|{debian_apt_mirror}|g' "
            f"-e 's|https://deb.debian.org/debian|{debian_apt_mirror}|g' "
            f"-e 's|http://security.debian.org/debian-security|{debian_apt_mirror}-security|g' "
            f"-e 's|https://security.debian.org/debian-security|{debian_apt_mirror}-security|g' {{}} +; fi\n"
        )
    patched, count = re.subn(r"(?m)^(FROM[^\r\n]+\r?\n)", r"\1" + mirror_layer + retry_layer, source)
    if count == 0:
        return dockerfile
    patched = _wrap_network_install_instructions(patched)
    temporary = dockerfile.with_name(".skillrevise-retry.Dockerfile")
    temporary.write_text(patched, encoding="utf-8")
    return temporary


def _wrap_network_install_instructions(source: str) -> str:
    """Wrap network-sensitive package installation instructions with retries."""

    lines = source.splitlines(keepends=True)
    rendered: list[str] = []
    index = 0
    while index < len(lines):
        block = [lines[index]]
        index += 1
        # Docker removes a comment embedded in a backslash-continued
        # instruction.  Consume that comment and the following package line,
        # but do not let a standalone comment swallow the next RUN command.
        while block[-1].rstrip("\r\n").rstrip().endswith("\\") and index < len(lines):
            block.append(lines[index])
            index += 1
            while block[-1].lstrip().startswith("#") and index < len(lines):
                block.append(lines[index])
                index += 1
        instruction = "".join(block)
        if re.match(r"^\s*RUN\s+", instruction) and "apt-get update" in instruction and "apt-get install" in instruction:
            rendered.append(_wrap_apt_install_instruction(instruction))
        elif re.match(r"^\s*RUN\s+", instruction) and re.search(r"\bpip(?:3)?\s+install\b", instruction):
            rendered.append(_wrap_pip_install_instruction(instruction))
        else:
            rendered.append(instruction)
    return "".join(rendered)


def _wrap_apt_install_instruction(instruction: str) -> str:
    """Return one Docker RUN instruction with five complete install attempts."""

    command = re.sub(r"^\s*RUN\s+", "", instruction, count=1).rstrip()
    # Comments are valid between Dockerfile continuation lines but would turn
    # into shell comments after the RUN instruction is wrapped in parentheses.
    command = re.sub(r"(?m)^\s*#.*(?:\r?\n|$)", "", command)
    return (
        "RUN --mount=type=cache,target=/var/cache/apt,sharing=locked "
        "--mount=type=cache,target=/var/lib/apt,sharing=locked attempt=1; \\\n"
        "    while [ \"$attempt\" -le 5 ]; do \\\n"
        f"      ( {command} ) && exit 0; \\\n"
        "      attempt=$((attempt + 1)); \\\n"
        "      if [ \"$attempt\" -le 5 ]; then rm -rf /var/lib/apt/lists/*; sleep 5; fi; \\\n"
        "    done; \\\n"
        "    exit 1\n"
    )


def _wrap_pip_install_instruction(instruction: str) -> str:
    """Retry complete pip installation transactions with a longer read timeout."""

    command = re.sub(r"^\s*RUN\s+", "", instruction, count=1).rstrip()
    return (
        "RUN attempt=1; \\\n"
        "    while [ \"$attempt\" -le 5 ]; do \\\n"
        f"      ( PIP_DEFAULT_TIMEOUT=120 PIP_RETRIES=5 {command} ) && exit 0; \\\n"
        "      attempt=$((attempt + 1)); \\\n"
        "      if [ \"$attempt\" -le 5 ]; then sleep 5; fi; \\\n"
        "    done; \\\n"
        "    exit 1\n"
    )


def _start_container(image_tag: str, workspace: Path, timeout_seconds: int) -> tuple[str, str]:
    name = f"skillrevise-agent-{uuid4().hex[:12]}"
    result = _run_command(
        [
            "docker",
            "run",
            "--detach",
            "--rm",
            "--name",
            name,
            "--user",
            "root",
            "--volume",
            f"{workspace}:/workspace",
            "--entrypoint",
            "/bin/sh",
            image_tag,
            "-lc",
            "while true; do sleep 3600; done",
        ],
        timeout_seconds=timeout_seconds,
    )
    if result.returncode != 0:
        raise HarnessError(f"Docker container failed to start: {_tail(result.stderr or result.stdout)}")
    container_id = result.stdout.strip()
    if not container_id:
        raise HarnessError("Docker did not return a container id.")
    workdir = _run_command(
        ["docker", "image", "inspect", image_tag, "--format", "{{.Config.WorkingDir}}"],
        timeout_seconds=timeout_seconds,
    )
    return container_id, workdir.stdout.strip() or "/"


def _copy_verifier_files(container_id: str, workspace: Path, timeout_seconds: int) -> None:
    tests = workspace / "tests"
    if not tests.is_dir():
        raise HarnessError(f"Task workspace has no tests directory: {tests}")
    setup = _run_command(
        ["docker", "exec", container_id, "/bin/sh", "-lc", "rm -rf /tests; mkdir -p /logs/verifier"],
        timeout_seconds=timeout_seconds,
    )
    if setup.returncode != 0:
        raise HarnessError(f"Could not prepare verifier paths: {_tail(setup.stderr)}")
    copied = _run_command(
        ["docker", "cp", str(tests), f"{container_id}:/tests"],
        timeout_seconds=timeout_seconds,
    )
    if copied.returncode != 0:
        raise HarnessError(f"Could not copy verifier tests: {_tail(copied.stderr)}")
    normalized = _run_command(
        [
            "docker",
            "exec",
            container_id,
            "/bin/sh",
            "-lc",
            "find /tests -type f -name '*.sh' -exec sed -i 's/\\r$//' {} +",
        ],
        timeout_seconds=timeout_seconds,
    )
    if normalized.returncode != 0:
        raise HarnessError(f"Could not normalize verifier shell scripts: {_tail(normalized.stderr)}")


def _run_verifier(container_id: str, timeout_seconds: int) -> CommandResult:
    return _run_command(
        ["docker", "exec", container_id, "/bin/sh", "-lc", "bash /tests/test.sh"],
        timeout_seconds=max(timeout_seconds, 600),
    )


def _read_reward(container_id: str, timeout_seconds: int) -> float:
    result = _run_command(
        ["docker", "exec", container_id, "/bin/sh", "-lc", "cat /logs/verifier/reward.txt 2>/dev/null || true"],
        timeout_seconds=timeout_seconds,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def _remove_container(container_id: str) -> None:
    try:
        _run_command(["docker", "rm", "--force", container_id], timeout_seconds=30)
    except Exception:
        pass


def _remove_image(image_tag: str) -> None:
    try:
        _run_command(["docker", "image", "rm", "--force", image_tag], timeout_seconds=60)
    except Exception:
        pass


def _chat_completion(
    config: ExecutorConfig,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
) -> dict[str, Any]:
    payload = _chat_completion_payload(config, messages, tools)
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{config.base_url}/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {config.api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=config.model_timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise HarnessError(f"Executor API returned HTTP {exc.code}: {detail[:500]}") from exc
    except urllib.error.URLError as exc:
        raise HarnessError(f"Executor API request failed: {exc}") from exc
    try:
        response = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise HarnessError(f"Executor API returned invalid JSON: {response_body[:500]}") from exc
    if not isinstance(response, dict):
        raise HarnessError("Executor API response was not an object.")
    return response


def _chat_completion_payload(
    config: ExecutorConfig,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a Chat Completions payload compatible with GPT-5 reasoning models."""

    payload: dict[str, Any] = {
        "model": config.model,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
    }
    is_new_openai_model = _is_openai_new_completion_model(config.model)
    payload["max_completion_tokens" if is_new_openai_model else "max_tokens"] = config.max_tokens
    if not (is_new_openai_model and config.reasoning_effort not in {None, "none"}):
        payload["temperature"] = config.temperature
    if is_new_openai_model and config.reasoning_effort:
        payload["reasoning_effort"] = config.reasoning_effort
    if config.seed is not None:
        payload["seed"] = config.seed
    return payload


def _shell_tool_schema() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "shell",
                "description": "Run a shell command inside the isolated task container.",
                "parameters": {
                    "type": "object",
                    "properties": {"command": {"type": "string", "description": "Shell command to execute."}},
                    "required": ["command"],
                    "additionalProperties": False,
                },
            },
        }
    ]


def _first_choice(response: Mapping[str, Any]) -> dict[str, Any]:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise HarnessError(f"Executor response contained no choices: {json.dumps(response)[:500]}")
    return choices[0]


def _tool_command(raw_call: Any) -> str:
    if not isinstance(raw_call, dict):
        raise HarnessError("Executor returned an invalid tool call.")
    function = raw_call.get("function")
    if not isinstance(function, dict) or function.get("name") != "shell":
        raise HarnessError("Executor requested an unsupported tool.")
    arguments = _parse_tool_arguments(function.get("arguments", "{}"))
    command = arguments.get("command")
    if not isinstance(command, str) or not command.strip():
        raise HarnessError("Executor shell tool call did not include a command.")
    return command


def _parse_tool_arguments(value: Any) -> dict[str, str]:
    """Accept common non-standard function argument encodings from executors."""

    if isinstance(value, Mapping):
        parsed: Any = dict(value)
    elif isinstance(value, str):
        text = value.strip()
        if text.startswith("```") and text.endswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        candidates = [text]
        if "{" in text and "}" in text:
            candidates.append(text[text.find("{") : text.rfind("}") + 1])
        parsed = None
        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
                break
            except json.JSONDecodeError:
                try:
                    parsed = ast.literal_eval(candidate)
                    break
                except (SyntaxError, ValueError):
                    pass
        if parsed is None and text and "{" not in text:
            parsed = {"command": text}
    else:
        parsed = None
    if not isinstance(parsed, Mapping):
        raise HarnessError("Executor supplied invalid shell tool arguments.")
    for key in ("command", "cmd", "shell"):
        command = parsed.get(key)
        if isinstance(command, str) and command.strip():
            return {"command": command}
    raise HarnessError("Executor shell tool call did not include a command.")


def _run_command(argv: list[str], *, timeout_seconds: int) -> CommandResult:
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        raise HarnessError(f"Required command is not available: {argv[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        stdout = _coerce_output(exc.stdout)
        stderr = _coerce_output(exc.stderr)
        return CommandResult(124, stdout, stderr or f"Command timed out after {timeout_seconds} seconds.")
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def _required_path(name: str) -> Path:
    value = _required_text(name)
    path = Path(value)
    if not path.is_dir():
        raise HarnessError(f"{name} is not a directory: {path}")
    return path


def _required_text(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise HarnessError(f"Missing {name}.")
    return value


def _read_optional_skill(value: str) -> str | None:
    if not value.strip():
        return None
    path = Path(value)
    if not path.is_file():
        raise HarnessError(f"Skill path does not exist: {path}")
    return path.read_text(encoding="utf-8")


def _agent_system_prompt() -> str:
    return """You are an execution agent inside an isolated benchmark Docker container.
Use the shell tool to inspect files, solve the task, and validate your work. Work in the
image's current working directory unless task evidence requires another location. The
host task bundle is visible at /workspace; it contains instruction.md, environment/, and
tests/. The final verifier runs as `bash /tests/test.sh` in the image working directory.
Do not claim success without running relevant checks. Keep all actions inside the container
and do not attempt to access host credentials, Docker sockets, or external task directories."""


def _agent_task_prompt(*, instruction: str, skill_text: str | None, working_directory: str) -> str:
    skill_section = "No external skill is supplied for this baseline run."
    if skill_text:
        skill_section = f"Use this external skill as guidance, but verify it against the environment:\n\n{skill_text}"
    return "\n\n".join(
        [
            f"Task instruction:\n{instruction}",
            f"The image working directory is {working_directory!r}.",
            skill_section,
            "Solve the task now. Inspect before assuming paths or commands, create the required output in the verifier-visible location, and run focused checks before you finish.",
        ]
    )


def _event(index: int, kind: str, summary: str, evidence: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "step_index": index,
        "kind": kind,
        "summary": summary,
        "evidence": evidence,
        "metadata": metadata or {},
    }


def _write_trace(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _usage_total_tokens(value: Any) -> int:
    if not isinstance(value, Mapping):
        return 0
    total = value.get("total_tokens")
    try:
        return max(0, int(total))
    except (TypeError, ValueError):
        return 0


def _positive_int(env: Mapping[str, str], name: str, default: int) -> int:
    value = env.get(name, "")
    if not value:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise HarnessError(f"{name} must be an integer, got {value!r}.") from exc
    if parsed < 1:
        raise HarnessError(f"{name} must be at least 1, got {parsed}.")
    return parsed


def _optional_int(env: Mapping[str, str], name: str) -> int | None:
    value = env.get(name, "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise HarnessError(f"{name} must be an integer, got {value!r}.") from exc


def _optional_reasoning_effort(env: Mapping[str, str], name: str) -> str | None:
    value = env.get(name, "").strip().lower()
    if not value:
        return None
    allowed = {"none", "low", "medium", "high", "xhigh"}
    if value not in allowed:
        raise HarnessError(f"{name} must be one of {sorted(allowed)}, got {value!r}.")
    return value


def _is_openai_new_completion_model(model: str) -> bool:
    return model.strip().lower().startswith(("gpt-5", "o1", "o3", "o4"))


def _float(env: Mapping[str, str], name: str, default: float) -> float:
    value = env.get(name, "")
    if not value:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise HarnessError(f"{name} must be a number, got {value!r}.") from exc


def _safe_name(value: str) -> str:
    return re.sub(r"[^a-z0-9_.-]+", "-", value.lower()).strip("-") or "task"


def _tail(value: str, limit: int = MAX_TOOL_OUTPUT_CHARS) -> str:
    return value[-limit:].strip()


def _coerce_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value


def _summarize_verifier(result: CommandResult, reward: float) -> str:
    text = _tail(result.stdout or result.stderr, 500)
    state = "passed" if result.returncode == 0 and reward >= 1.0 else "failed"
    return f"Verifier {state} (exit={result.returncode}, reward={reward:g})." + (f" Last output: {text}" if text else "")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    main()
