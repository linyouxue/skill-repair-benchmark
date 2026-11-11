"""Executor for the raw single-Skill handoff task layout.

This harness accepts a task workspace with ``task.md``, ``environment/``,
``verifier/`` and optional ``oracle/``.  It intentionally does not mount the
host workspace in the agent container: task inputs are supplied by the image's
Dockerfile, while verifier files are copied only after the agent finishes.
That keeps ``oracle/`` and verifier implementation details out of the agent's
shell while preserving the handoff package byte-for-byte on the host.

Run with ``python -m skillrevise.handoff_harness``.
"""

from __future__ import annotations

import json
import hashlib
import os
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from . import harness as base


HANDOFF_VERIFIER_DIR = "verifier"


def main() -> None:
    """Execute one raw handoff task and emit SkillRevise's trace schema."""

    started = time.monotonic()
    started_at = base._utc_now()
    trace_path = Path(os.environ.get("SKILL_REVISE_TRACE_PATH", "handoff_harness_trace.json"))
    task_id = os.environ.get("SKILL_REVISE_TASK_ID", "unknown-task")
    events: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {"harness": "raw-handoff-docker"}
    tokens = 0
    tool_calls = 0
    outcome_summary = "Handoff harness did not run."
    exit_code = 2
    container_id: str | None = None
    image_tag: str | None = None
    remove_image_after_run = False

    try:
        config = base.load_executor_config(os.environ)
        metadata["executor_config"] = _executor_config_metadata(config)
        workspace = base._required_path("SKILL_REVISE_WORKSPACE")
        _validate_handoff_workspace(workspace)
        instruction = base._required_text("SKILL_REVISE_INSTRUCTION")
        skill_text = base._read_optional_skill(os.environ.get("SKILL_REVISE_SKILL_PATH", ""))
        if skill_text is not None:
            skill_sha256 = hashlib.sha256(skill_text.encode("utf-8")).hexdigest()
            metadata["skill_context"] = {"sha256": skill_sha256, "characters": len(skill_text)}
            events.append(
                base._event(
                    len(events) + 1,
                    "skill_context",
                    "Injected the supplied initial Skill into the execution agent's task context.",
                    f"SHA-256: {skill_sha256}",
                    {"sha256": skill_sha256, "characters": len(skill_text)},
                )
            )

        image_tag, remove_image_after_run = base._build_task_image(
            workspace,
            task_id,
            config.command_timeout_seconds,
        )
        prepared_tag = _prepared_image_tag(workspace, image_tag)
        using_prepared_image = base._docker_image_exists(prepared_tag, config.command_timeout_seconds)
        if using_prepared_image:
            image_tag = prepared_tag
            remove_image_after_run = False
        container_id, working_directory = _start_isolated_container(
            image_tag,
            config.command_timeout_seconds,
        )

        agent = base.DockerToolAgent(
            config=config,
            container_id=container_id,
            working_directory=working_directory,
            system_prompt=_handoff_agent_system_prompt(),
        )
        agent_result = agent.solve(instruction=instruction, skill_text=skill_text)
        events.extend(agent_result["events"])
        tokens = agent_result["tokens"]
        tool_calls = agent_result["tool_calls"]
        metadata.update(
            {
                "image_tag": image_tag,
                "agent_final": agent_result["final"],
            }
        )

        # Copy the verifier only after the agent is done, so it cannot inspect
        # implementation-specific expected values while solving the task.
        _copy_handoff_verifier(container_id, workspace, config.command_timeout_seconds)
        verifier = _run_handoff_verifier(
            container_id,
            config.command_timeout_seconds,
            use_prepared_dependencies=using_prepared_image,
        )
        reward = base._read_reward(container_id, config.command_timeout_seconds)
        _write_verifier_result(
            container_id,
            trace_path.parent,
            verifier,
            reward,
            config.command_timeout_seconds,
        )
        copied_outputs = _snapshot_outputs(
            container_id,
            workspace,
            task_id,
            trace_path.parent / "outputs",
            config.command_timeout_seconds,
        )
        metadata["outputs"] = copied_outputs
        success = verifier.returncode == 0 and reward >= 1.0
        exit_code = 0 if success else 1
        outcome_summary = base._summarize_verifier(verifier, reward)
        events.append(
            base._event(
                len(events) + 1,
                "verifier",
                outcome_summary,
                base._tail(verifier.stdout + "\n" + verifier.stderr),
                {"exit_code": verifier.returncode, "reward": reward},
            )
        )
        events.append(
            base._event(
                len(events) + 1,
                "artifact_output",
                _output_snapshot_summary(copied_outputs),
                "",
                {"outputs": copied_outputs},
            )
        )
        metadata["reward"] = reward
        metadata["verifier_exit_code"] = verifier.returncode
    except Exception as exc:  # Always return a diagnostic trace to SkillRevise.
        outcome_summary = f"Handoff harness error: {exc}"
        metadata["reward"] = 0.0
        metadata["harness_error"] = str(exc)
        events.append(base._event(len(events) + 1, "harness_error", outcome_summary, ""))
        exit_code = 2
    finally:
        if container_id:
            base._remove_container(container_id)
        if image_tag and remove_image_after_run:
            base._remove_image(image_tag)
        base._write_trace(
            trace_path,
            {
                "tokens": tokens,
                "tool_calls": tool_calls,
                "steps": len(events),
                "latency_seconds": round(time.monotonic() - started, 4),
                "outcome_summary": outcome_summary,
                "events": events,
                "metadata": metadata | {"started_at": started_at, "ended_at": base._utc_now()},
            },
        )

    raise SystemExit(exit_code)


def _validate_handoff_workspace(workspace: Path) -> None:
    missing = [name for name in ("task.md", "environment", HANDOFF_VERIFIER_DIR) if not (workspace / name).exists()]
    if missing:
        raise base.HarnessError(
            f"Raw handoff workspace must contain task.md, environment/, and {HANDOFF_VERIFIER_DIR}/; missing: {', '.join(missing)}"
        )


def _executor_config_metadata(config: base.ExecutorConfig) -> dict[str, Any]:
    """Return the reproducibility-relevant executor settings without its API key."""

    return {
        "base_url": config.base_url,
        "model": config.model,
        "max_tool_calls": config.max_tool_calls,
        "http_timeout_seconds": config.model_timeout_seconds,
        "command_timeout_seconds": config.command_timeout_seconds,
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
        "seed": config.seed,
    }


def _write_verifier_result(
    container_id: str,
    artifact_dir: Path,
    verifier: base.CommandResult,
    reward: float,
    timeout_seconds: int,
) -> None:
    """Persist the handoff verifier's score and individual CTRF test outcomes.

    The handoff harness is the verifier, so the adapter deliberately skips a
    second host-side verifier.  This file gives it the same durable structured
    verifier record as ordinary SkillsBench runs.
    """

    artifact_dir.mkdir(parents=True, exist_ok=True)
    ctrf_path = artifact_dir / "verifier_ctrf.json"
    copied = base._run_command(
        ["docker", "cp", f"{container_id}:/logs/verifier/ctrf.json", str(ctrf_path)],
        timeout_seconds=timeout_seconds,
    )
    ctrf_error = ""
    if copied.returncode != 0:
        ctrf_error = base._tail(copied.stderr or copied.stdout)
        ctrf_path.unlink(missing_ok=True)

    passed_checks: list[str] = []
    failed_checks: list[str] = []
    report_summary: dict[str, Any] = {}
    if ctrf_path.is_file():
        try:
            ctrf = json.loads(ctrf_path.read_text(encoding="utf-8"))
            passed_checks, failed_checks, report_summary = _ctrf_check_outcomes(ctrf)
        except (OSError, json.JSONDecodeError) as exc:
            ctrf_error = f"Could not parse CTRF report: {exc}"

    base._write_trace(
        artifact_dir / "verifier_result.json",
        {
            "success": verifier.returncode == 0 and reward >= 1.0,
            "total_score": reward,
            "reward": reward,
            "exit_code": verifier.returncode,
            "passed_checks": passed_checks,
            "failed_checks": failed_checks,
            "summary": report_summary,
            "stdout": verifier.stdout,
            "stderr": verifier.stderr,
            "ctrf_path": ctrf_path.name if ctrf_path.is_file() else None,
            "ctrf_error": ctrf_error or None,
        },
    )


def _ctrf_check_outcomes(payload: Any) -> tuple[list[str], list[str], dict[str, Any]]:
    """Extract a compact passed/failed list from pytest-json-ctrf output."""

    results = payload.get("results", {}) if isinstance(payload, dict) else {}
    tests = results.get("tests", []) if isinstance(results, dict) else []
    summary = results.get("summary", {}) if isinstance(results, dict) else {}
    passed: list[str] = []
    failed: list[str] = []
    for index, test in enumerate(tests if isinstance(tests, list) else [], start=1):
        if not isinstance(test, dict):
            continue
        name = str(test.get("name") or test.get("fullName") or test.get("id") or f"check-{index}")
        status = str(test.get("status") or test.get("outcome") or "").lower()
        if status in {"passed", "pass", "success"}:
            passed.append(name)
        elif status:
            failed.append(name)
    return passed, failed, summary if isinstance(summary, dict) else {}


def _start_isolated_container(image_tag: str, timeout_seconds: int) -> tuple[str, str]:
    """Start the task image without exposing the host task bundle to the agent."""

    name = f"skillrevise-handoff-{uuid4().hex[:12]}"
    result = base._run_command(
        [
            "docker",
            "run",
            "--detach",
            "--rm",
            "--name",
            name,
            "--user",
            "root",
            "--entrypoint",
            "/bin/sh",
            image_tag,
            "-lc",
            "while true; do sleep 3600; done",
        ],
        timeout_seconds=timeout_seconds,
    )
    if result.returncode != 0:
        raise base.HarnessError(f"Docker container failed to start: {base._tail(result.stderr or result.stdout)}")
    container_id = result.stdout.strip()
    if not container_id:
        raise base.HarnessError("Docker did not return a container id.")
    workdir = base._run_command(
        ["docker", "image", "inspect", image_tag, "--format", "{{.Config.WorkingDir}}"],
        timeout_seconds=timeout_seconds,
    )
    return container_id, workdir.stdout.strip() or "/"


def _copy_handoff_verifier(container_id: str, workspace: Path, timeout_seconds: int) -> None:
    verifier = workspace / HANDOFF_VERIFIER_DIR
    setup = base._run_command(
        ["docker", "exec", container_id, "/bin/sh", "-lc", _verifier_setup_command()],
        timeout_seconds=timeout_seconds,
    )
    if setup.returncode != 0:
        raise base.HarnessError(f"Could not prepare verifier paths: {base._tail(setup.stderr)}")
    copied = base._run_command(
        ["docker", "cp", str(verifier), f"{container_id}:/verifier"],
        timeout_seconds=timeout_seconds,
    )
    if copied.returncode != 0:
        raise base.HarnessError(f"Could not copy handoff verifier: {base._tail(copied.stderr)}")
    normalized = base._run_command(
        [
            "docker",
            "exec",
            container_id,
            "/bin/sh",
            "-lc",
            "ln -s /verifier /tests && find /verifier -type f -name '*.sh' -exec sed -i 's/\\r$//' {} +",
        ],
        timeout_seconds=timeout_seconds,
    )
    if normalized.returncode != 0:
        raise base.HarnessError(f"Could not normalize verifier shell scripts: {base._tail(normalized.stderr)}")


def _verifier_setup_command() -> str:
    """Prepare isolated verifier paths and make transient apt downloads retryable."""

    return (
        "rm -rf /tests /verifier; "
        "mkdir -p /logs/verifier /etc/apt/apt.conf.d; "
        "printf '%s\\n' "
        "'Acquire::Retries \"5\";' "
        "'Acquire::http::Timeout \"60\";' "
        "'Acquire::https::Timeout \"60\";' "
        "> /etc/apt/apt.conf.d/99-skillrevise-verifier-retries"
    )


def _prepared_image_tag(workspace: Path, base_image_tag: str) -> str:
    """Return a verifier-dependency cache tag keyed by the raw verifier files."""

    digest = hashlib.sha256()
    verifier = workspace / HANDOFF_VERIFIER_DIR
    for path in sorted((item for item in verifier.rglob("*") if item.is_file()), key=lambda item: item.as_posix()):
        digest.update(path.relative_to(verifier).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return f"{base_image_tag}-verifier-{digest.hexdigest()[:12]}"


def _run_handoff_verifier(
    container_id: str,
    timeout_seconds: int,
    *,
    use_prepared_dependencies: bool,
) -> base.CommandResult:
    """Run the unchanged verifier, skipping only already-preflighted installers."""

    if not use_prepared_dependencies:
        return base._run_verifier(container_id, timeout_seconds)
    command = (
        "mkdir -p /skillrevise-preflight-bin; "
        "printf '#!/bin/sh\\nexit 0\\n' > /skillrevise-preflight-bin/apt-get; "
        "printf '#!/bin/sh\\nexit 0\\n' > /skillrevise-preflight-bin/curl; "
        "chmod 0755 /skillrevise-preflight-bin/apt-get /skillrevise-preflight-bin/curl; "
        "PATH=/skillrevise-preflight-bin:$PATH bash /tests/test.sh"
    )
    return base._run_command(
        ["docker", "exec", container_id, "/bin/sh", "-lc", command],
        timeout_seconds=max(timeout_seconds, 600),
    )


def _snapshot_outputs(
    container_id: str,
    workspace: Path,
    task_id: str,
    destination: Path,
    timeout_seconds: int,
) -> list[dict[str, str | bool]]:
    """Copy verifier-visible task outputs before the ephemeral container is removed."""

    output_paths = _container_output_paths(workspace, task_id)
    results: list[dict[str, str | bool]] = []
    for container_path, relative_destination in output_paths:
        target = destination / relative_destination
        target.parent.mkdir(parents=True, exist_ok=True)
        copied = base._run_command(
            ["docker", "cp", f"{container_id}:{container_path}", str(target)],
            timeout_seconds=timeout_seconds,
        )
        results.append(
            {
                "container_path": container_path,
                "artifact_path": str(target),
                "copied": copied.returncode == 0,
                "detail": base._tail(copied.stderr or copied.stdout, 500),
            }
        )
    return results


def _container_output_paths(workspace: Path, task_id: str) -> list[tuple[str, Path]]:
    if task_id == "manufacturing-codebook-normalization":
        return [("/app/output/solution.json", Path("manufacturing") / "solution.json")]
    if task_id != "pddl-tpp-planning":
        return []

    problem_path = workspace / "environment" / "problem.json"
    entries = json.loads(problem_path.read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise base.HarnessError(f"PDDL problem.json must be a list: {problem_path}")
    paths: list[tuple[str, Path]] = []
    for entry in entries:
        output = entry.get("plan_output") if isinstance(entry, dict) else None
        if not isinstance(output, str) or not output.strip():
            raise base.HarnessError(f"PDDL task has no plan_output: {entry!r}")
        relative = Path(output)
        if relative.is_absolute() or ".." in relative.parts:
            raise base.HarnessError(f"Unsafe PDDL plan_output path: {output}")
        paths.append((f"/app/{relative.as_posix()}", Path("pddl") / relative))
    return paths


def _output_snapshot_summary(outputs: list[dict[str, str | bool]]) -> str:
    copied = sum(item["copied"] is True for item in outputs)
    return f"Archived {copied}/{len(outputs)} verifier-visible output files."


def _handoff_agent_system_prompt() -> str:
    return """You are an execution agent inside an isolated benchmark Docker container.
Use the shell tool to inspect the files already installed in the image, solve the task,
and run focused self-checks. Work in the image's current working directory unless task
evidence requires another location. The task instruction and optional Skill are provided
in this conversation. The verifier and any oracle/reference solution are deliberately not
available while you solve the task. Create the required output in its verifier-visible
location. Do not claim success without checking your own output. Keep all actions inside
the container and do not attempt to access host credentials, Docker sockets, or external
directories."""


if __name__ == "__main__":
    main()
