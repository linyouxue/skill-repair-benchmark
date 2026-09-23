"""Repair a failed SkillsBench command by CausalFlow-style branching.

The script consumes a completed failed rollout, identifies the last command
that writes a verifier-referenced artifact, asks an OpenRouter model for a
minimal replacement, then evaluates the original trace and each repair in
fresh copies of the unmodified task image with the official verifier.

Only task.md, deployed skills, the recorded command and verifier stdout are
shown to the repair model.  Verifier source and expected-answer files are used
for execution only and are never included in the repair prompt.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from repro_wrappers.diagnose_openrouter import (  # noqa: E402
    API_ROOT,
    load_key,
    request_json,
    safe_error,
)
from repro_wrappers.run_skillsbench_openrouter_smoke import (  # noqa: E402
    container_proxy_env,
)
from skillsbench_replay.atif import load_run, materialize_replay_command  # noqa: E402
from skillsbench_replay.openrouter_acp_agent import (  # noqa: E402
    content_digest,
    snapshot_path_ignored,
)
from skillsbench_replay.graph import (  # noqa: E402
    SkillsBenchGraphBuilder,
    infer_task_workspace,
    infer_verifier_reads,
    resource_ids_for_paths,
)
from skillsbench_replay.planner import ReplayPlanner  # noqa: E402
from replay_graph.builder import step_node_id  # noqa: E402
from replay_graph.schema import NodeKind  # noqa: E402


SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
SCRIPT_LAUNCH_RE = re.compile(
    r"^\s*(?:python(?:3(?:\.\d+)?)?|bash|sh|node)\s+([^\s;&|]+)"
)
MAX_CONTEXT_CHARS = 60_000
MAX_COMMAND_CHARS = 30_000
MAX_FEEDBACK_CHARS = 12_000
RETURN_CODE_RE = re.compile(r"(?:^|\n)(?:return_code=|(?:✅ |❌ )?Exit code\s*:\s*)(-?\d+)(?:\r?\n|$)")


SYSTEM_PROMPT = """You repair one causal command in a failed terminal-agent trace.

Return one JSON object with these fields:
{
  "diagnosis": "specific logical cause of the observed failure",
  "repaired_command": "complete executable replacement shell command",
  "changes": ["short concrete change"],
  "minimality_reason": "why the edit is limited to the diagnosed fault"
}

Rules:
- Repair only the target command. Preserve its output paths and output format.
- Use the task, skills, recorded trace and verifier feedback as evidence.
- Do not invent hidden requirements or claim access to verifier source.
- Return a complete command, not a diff and not Markdown.
- The command runs inside a disposable benchmark container.
- Prefer a small logical correction over rewriting unrelated working logic.
"""


def _safe_name(value: str, label: str) -> str:
    if not SAFE_NAME_RE.fullmatch(value):
        raise ValueError(f"unsafe {label}: {value!r}")
    return value


def _read_skills(skills_root: Path) -> str:
    chunks: list[str] = []
    used = 0
    # Include referenced Markdown pages as well as the top-level skill.  The
    # repair target is chosen by the graph first; this only expands the
    # evidence available inside that deployed skill bundle.
    paths = sorted(
        skills_root.rglob("*.md"),
        key=lambda path: (path.name != "SKILL.md", str(path)),
    )
    for path in paths:
        header = f"\n===== {path.relative_to(skills_root)} =====\n"
        text = path.read_text(errors="replace")
        remaining = MAX_CONTEXT_CHARS - used
        if remaining <= 0:
            break
        chunk = (header + text)[:remaining]
        chunks.append(chunk)
        used += len(chunk)
    return "".join(chunks)


def _verifier_feedback(run_dir: Path) -> str:
    candidates = (
        run_dir / "verifier" / "test-stdout.txt",
        run_dir / "verifier" / "test-stderr.txt",
    )
    chunks = []
    for path in candidates:
        if path.exists():
            chunks.append(f"===== {path.name} =====\n{path.read_text(errors='replace')}")
    return "\n".join(chunks)[-MAX_FEEDBACK_CHARS:]


def _workspace_aliases(path: str) -> tuple[str, ...]:
    normalized = path.rstrip("/")
    aliases = [normalized]
    for root in ("/root/", "/app/", "/workspace/"):
        if normalized.startswith(root):
            aliases.append(normalized[len(root) :])
    return tuple(dict.fromkeys(aliases))


def _paths_related(left: str, right: str) -> bool:
    return any(
        a == b or a.startswith(b + "/") or b.startswith(a + "/")
        for a in _workspace_aliases(left)
        for b in _workspace_aliases(right)
    )


def _target_event(parsed, verifier_paths: tuple[str, ...]):
    normalized = tuple(path.rstrip("/") for path in verifier_paths)
    artifact_event = None
    for event in reversed(parsed.events):
        writes = tuple(dict.fromkeys((*event.observed_writes, *event.inferred_writes)))
        if any(
            _paths_related(write, verifier)
            for write in writes
            for verifier in normalized
        ):
            artifact_event = event
            break
    if artifact_event is not None:
        # A short launcher such as ``python /root/solve.py`` may write the
        # graded artifact, while the actual decision logic lives in the most
        # recent command that created that script.  Branch at the writer and
        # retain the launcher as a downstream consumer.
        launch = SCRIPT_LAUNCH_RE.match(artifact_event.command or "")
        script_path = launch.group(1).strip("'\"") if launch else ""
        if (
            script_path
            and script_path != "-"
            and len(artifact_event.command or "") <= 1_000
        ):
            script = script_path.rstrip("/")
            # CommandEvent is a dataclass.  Two repeated launcher events can
            # compare equal, so ``list.index`` may return an older execution
            # and hide the newest script writer.  Locate this exact object.
            artifact_index = next(
                index
                for index, event in enumerate(parsed.events)
                if event is artifact_event
            )
            for event in reversed(parsed.events[:artifact_index]):
                writes = tuple(
                    dict.fromkeys((*event.observed_writes, *event.inferred_writes))
                )
                if any(
                    write.rstrip("/") == script
                    or write.rstrip("/").endswith("/" + script)
                    or script.endswith("/" + write.rstrip("/"))
                    or Path(write.rstrip("/")).name == Path(script).name
                    for write in writes
                ):
                    return event
        return artifact_event
    for event in reversed(parsed.events):
        if event.command and (event.observed_writes or event.inferred_writes):
            return event
    # Tool-budget failures can stop immediately before the final artifact is
    # written.  In that case branch at the last executable decision and give
    # the repair model the preceding trace, so it can replace exploration with
    # the missing finalization command.
    for event in reversed(parsed.events):
        if event.command:
            return event
    raise ValueError("no replayable command found")


def _trace_context(parsed, target_step: int) -> str:
    chunks = []
    for event in parsed.events:
        if event.step_id >= target_step:
            break
        command = (event.command or "[non-command event]")[:4_000]
        output = event.output[-2_500:]
        chunks.append(f"STEP {event.step_id}\nCOMMAND\n{command}\nOUTPUT\n{output}")
    return "\n\n".join(chunks)[-35_000:]


def _json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        lines = lines[1:] if lines else lines
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        start, end = stripped.find("{"), stripped.rfind("}")
        if start < 0 or end <= start:
            raise
        payload = json.loads(stripped[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("repair response is not an object")
    command = payload.get("repaired_command")
    if not isinstance(command, str) or not command.strip():
        raise ValueError("repair response has no repaired_command")
    payload["repaired_command"] = command.strip()
    return payload


def _repair_prompt(
    *,
    task_text: str,
    skills_text: str,
    target_step: int,
    original_command: str,
    original_output: str,
    verifier_feedback: str,
    trace_context: str,
    earlier_repairs: list[dict[str, Any]],
) -> str:
    prior = ""
    if earlier_repairs:
        prior = (
            "\n\nEARLIER REPAIRS TO AVOID REPEATING\n"
            + "\n".join(
                (
                    f"- diagnosis={item.get('diagnosis', '')}; "
                    f"changes={item.get('changes', [])}; "
                    f"official_evaluation={item.get('_evaluation_feedback', 'not available')}"
                )
                for item in earlier_repairs
            )
        )
    return f"""TASK
{task_text[:12_000]}

DEPLOYED SKILLS
{skills_text}

RECORDED TRACE BEFORE THE TARGET
{trace_context}

CAUSAL TARGET
Step {target_step} is the selected branch point. It either writes the graded artifact or is the final decision before a missing artifact.

ORIGINAL COMMAND
{original_command[:MAX_COMMAND_CHARS]}

ORIGINAL COMMAND OUTPUT
{original_output[-4_000:]}

OFFICIAL VERIFIER FEEDBACK FROM THE FAILED RUN
{verifier_feedback}
{prior}
"""


def _call_repair_model(
    *,
    model: str,
    api_key: str,
    prompt: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for attempt in range(2):
        reminder = (
            "\n\nYour previous response had no final JSON. Use brief reasoning and "
            "emit the requested JSON object now."
            if attempt
            else ""
        )
        status, response = request_json(
            f"{API_ROOT}/chat/completions",
            api_key,
            payload={
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt + reminder},
                ],
                "temperature": 0.35,
                "max_tokens": 12_000,
                "reasoning": {"effort": "low", "exclude": True},
                "response_format": {"type": "json_object"},
            },
        )
        if status != 200:
            calls.append({"attempt": attempt + 1, "error": safe_error(response)})
            continue
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            calls.append({"attempt": attempt + 1, "error": "no choices"})
            continue
        choice = choices[0] if isinstance(choices[0], dict) else {}
        message = choice.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        calls.append(
            {
                "attempt": attempt + 1,
                "returned_model": response.get("model", model),
                "usage": response.get("usage", {}),
                "finish_reason": choice.get("finish_reason"),
                "has_content": isinstance(content, str) and bool(content.strip()),
            }
        )
        if isinstance(content, str) and content.strip():
            return _json_object(content), {
                "requested_model": model,
                "returned_model": response.get("model", model),
                "usage": response.get("usage", {}),
                "attempts": calls,
            }
    raise RuntimeError(f"repair model returned no usable content: {calls}")


def _build_image(task_dir: Path, image: str, timeout: int) -> dict[str, Any]:
    env = dict(os.environ)
    # BenchFlow uses BuildKit for these staged baselines.  Reuse the same
    # content-addressed cache so the formal adapter does not redownload an
    # unchanged environment with Docker's separate legacy-builder cache.
    env["DOCKER_BUILDKIT"] = "1"
    proxy_env: dict[str, str] = {}
    for name, value in container_proxy_env().items():
        proxy_env[name] = value
        proxy_env[name.lower()] = value
    command = ["docker", "build"]
    # HTTP(S)_PROXY and their lowercase forms are predefined Docker build
    # arguments and do not require ARG declarations in the task Dockerfile.
    # Forwarding them matches the staged BenchFlow baseline transport while
    # keeping proxy values out of image layers and experiment JSON.
    for name, value in proxy_env.items():
        command.extend(["--build-arg", f"{name}={value}"])
    command.extend(["-t", image, str(task_dir / "environment")])
    started = time.perf_counter()
    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
        env=env,
    )
    elapsed = time.perf_counter() - started
    if result.returncode != 0:
        raise RuntimeError(
            "task image build failed:\n" + (result.stdout + result.stderr)[-8000:]
        )
    return {
        "image": image,
        "seconds": elapsed,
        "build_backend": "buildkit",
        "build_proxy_forwarded": bool(proxy_env),
    }


def _read_reward(log_dir: Path) -> float | None:
    path = log_dir / "verifier" / "reward.txt"
    if not path.exists():
        return None
    try:
        return float(path.read_text().strip())
    except ValueError:
        return None


def _ctrf_counts(log_dir: Path) -> dict[str, int] | None:
    path = log_dir / "verifier" / "ctrf.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text())
    summary = payload.get("results", {}).get("summary", {})
    if not isinstance(summary, dict):
        return None
    return {
        key: int(summary.get(key) or 0)
        for key in ("tests", "passed", "failed", "skipped")
    }


def _task_resource_limits(task_dir: Path) -> dict[str, int | float]:
    """Read the official Docker CPU/memory limits from task frontmatter."""

    import yaml

    text = (task_dir / "task.md").read_text(errors="replace")
    if not text.startswith("---\n"):
        raise ValueError(f"task frontmatter is missing: {task_dir / 'task.md'}")
    try:
        raw, _body = text[4:].split("\n---\n", 1)
    except ValueError as exc:
        raise ValueError(
            f"task frontmatter is malformed: {task_dir / 'task.md'}"
        ) from exc
    frontmatter = yaml.safe_load(raw)
    sandbox = frontmatter.get("sandbox") if isinstance(frontmatter, dict) else None
    if sandbox is None and isinstance(frontmatter, dict):
        sandbox = frontmatter.get("environment")
    if not isinstance(sandbox, dict):
        raise ValueError(f"sandbox limits are missing: {task_dir / 'task.md'}")
    cpus = sandbox.get("cpus")
    memory_mb = sandbox.get("memory_mb")
    if not isinstance(cpus, (int, float)) or cpus <= 0:
        raise ValueError(f"invalid sandbox.cpus: {cpus!r}")
    if not isinstance(memory_mb, int) or memory_mb <= 0:
        raise ValueError(f"invalid sandbox.memory_mb: {memory_mb!r}")
    return {"cpus": cpus, "memory_mb": memory_mb}


def _recorded_return_codes(parsed) -> list[int | None]:
    values: list[int | None] = []
    for event in parsed.events:
        if not event.command:
            continue
        match = RETURN_CODE_RE.search(event.completion_output or event.output or "")
        values.append(int(match.group(1)) if match else None)
    return values


def _expected_final_write_hashes(parsed) -> tuple[dict[str, str], list[str]]:
    """Recover the original final hashes for every agent-written artifact."""

    hashes: dict[str, str] = {}
    missing: list[str] = []
    for event in parsed.events:
        for path in event.inferred_deletes:
            hashes.pop(path, None)
        for path in event.observed_writes:
            if snapshot_path_ignored(path):
                continue
            digest = event.observed_write_hashes.get(path)
            if digest:
                hashes[path] = digest
            else:
                missing.append(path)
    return hashes, sorted(set(missing))


def _replay_fidelity_report(
    parsed,
    replay: dict[str, Any],
    *,
    original_artifact_root: Path | None = None,
    expected_digest_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    expected_hashes, missing_hash_evidence = _expected_final_write_hashes(parsed)
    migrated_hashes: dict[str, dict[str, str]] = {}
    if original_artifact_root is not None:
        for path, recorded_digest in list(expected_hashes.items()):
            # Runs recorded before semantic Office/PNG/JSON digests may still
            # retain their submitted artifacts under ``agent/``.  Recompute
            # the expected digest from that original file instead of treating
            # every old raw SHA as incompatible with the new evidence format.
            artifact = original_artifact_root / path
            if not artifact.is_file():
                continue
            semantic_digest = content_digest(str(artifact))
            if semantic_digest != recorded_digest:
                expected_hashes[path] = semantic_digest
                migrated_hashes[path] = {
                    "recorded_raw_digest": recorded_digest,
                    "original_artifact_digest": semantic_digest,
                }
    verified_overrides: dict[str, dict[str, str]] = {}
    for path, digest in (expected_digest_overrides or {}).items():
        if path not in expected_hashes:
            raise ValueError(f"fidelity override targets an unrecorded path: {path}")
        verified_overrides[path] = {
            "recorded_digest": expected_hashes[path],
            "verified_replay_digest": digest,
        }
        expected_hashes[path] = digest
    actual_manifest = replay.get("workspace_manifest") or {}
    hash_mismatches = {
        path: {"expected": digest, "actual": actual_manifest.get(path)}
        for path, digest in expected_hashes.items()
        if actual_manifest.get(path) != digest
    }
    expected_codes = _recorded_return_codes(parsed)
    actual_records = replay.get("command_executions") or []
    actual_codes = [record.get("return_code") for record in actual_records]
    code_mismatches = [
        {
            "command_index": index,
            "expected": expected,
            "actual": actual_codes[index] if index < len(actual_codes) else None,
        }
        for index, expected in enumerate(expected_codes)
        if expected is not None
        and (index >= len(actual_codes) or actual_codes[index] != expected)
    ]
    command_events = [event for event in parsed.events if event.command]
    identity = replay.get("execution_identity")
    sandbox_identity_matches = (
        isinstance(identity, dict)
        and identity.get("agent_user") == "agent"
        and isinstance(identity.get("agent_uid"), int)
        and identity["agent_uid"] > 0
        and isinstance(identity.get("agent_gid"), int)
        and identity["agent_gid"] > 0
        and identity.get("agent_home") == "/home/agent"
        and identity.get("verifier_user") == "root"
    )
    non_lossless_steps = [
        event.step_id
        for event in command_events
        if event.argument_source != "result_marker"
    ]
    return {
        "lossless_command_markers": not non_lossless_steps,
        "non_lossless_command_steps": non_lossless_steps,
        "recorded_command_count": len(command_events),
        "replayed_command_count": len(actual_records),
        "command_count_matches": len(command_events) == len(actual_records),
        "recorded_return_codes": expected_codes,
        "replayed_return_codes": actual_codes,
        "return_codes_match": not code_mismatches,
        "return_code_mismatches": code_mismatches,
        "expected_final_write_hashes": expected_hashes,
        "migrated_original_artifact_hashes": migrated_hashes,
        "verified_replay_digest_overrides": verified_overrides,
        "missing_write_hash_evidence": missing_hash_evidence,
        "artifact_hashes_match": not missing_hash_evidence and not hash_mismatches,
        "artifact_hash_mismatches": hash_mismatches,
        "execution_identity": identity,
        "sandbox_identity_matches": sandbox_identity_matches,
    }


def _host_log_permissions_script(uid: int, gid: int) -> str:
    # These are disposable bind-mounted logs, not the task workspace.  Do not
    # follow links a replayed command may have placed in the log directory.
    return (
        f"chown -hR {uid}:{gid} /logs && "
        "find -P /logs -type d -exec chmod u+rwx {} + && "
        "find -P /logs -type f -exec chmod u+rw {} +"
    )


def _recover_host_log_permissions(logs: Path, image: str, *, force: bool) -> None:
    """Recover logs if a killed container could not run its EXIT trap."""

    if not force and logs.stat().st_uid == os.getuid():
        return
    subprocess.run(
        [
            "docker", "run", "--rm", "--network", "none", "--user", "0:0",
            "--entrypoint", "/bin/sh", "-v", f"{logs}:/logs", image, "-c",
            _host_log_permissions_script(os.getuid(), os.getgid()),
        ],
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    )


def _cached_verifier_uv(task_dir: Path) -> tuple[Path | None, str]:
    """Replace an exact pinned uv installer transport only, after replay."""

    installer = "https://astral.sh/uv/0.9.7/install.sh"
    expected_call = f"curl -LsSf {installer} | sh"
    verifier = task_dir / "verifier" / "test.sh"
    lines = verifier.read_text().splitlines() if verifier.is_file() else []
    if expected_call not in {line.strip() for line in lines}:
        if task_dir.name in {
            "seismic-phase-picking", "dynamic-object-aware-egomotion",
            "flink-query", "jpg-ocr-stat", "reserves-at-risk-calc",
        }:
            raise ValueError(f"{task_dir.name} verifier no longer uses the expected uv 0.9.7 installer")
        return None, ""
    # Same verified archive used by the original rollout's infra_support.py.
    archive = Path.home() / ".cache/benchmark-executor/uv-0.9.7-linux-x86_64.tar.gz"
    if not archive.is_file():
        raise FileNotFoundError(f"pinned verifier uv archive is missing: {archive}")
    script = (
        "mkdir -p /root/.local/bin || exit 125\n"
        "tar -xzf /causalflow-verifier-support/uv.tar.gz -C /root/.local/bin "
        "--strip-components=1 --no-same-owner || exit 125\n"
        "case \"$(/root/.local/bin/uv --version)\" in 'uv 0.9.7'|'uv 0.9.7 '*) ;; *) exit 125;; esac\n"
        "case \"$(/root/.local/bin/uvx --version)\" in 'uvx 0.9.7'|'uvx 0.9.7 '*) ;; *) exit 125;; esac\n"
        "printf 'export PATH=\"/root/.local/bin:$PATH\"\\n' > /root/.local/bin/env || exit 125\n"
        "curl() {\n"
        f"  if [ \"$#\" -eq 2 ] && [ \"$1\" = '-LsSf' ] && [ \"$2\" = '{installer}' ]; then\n"
        "    printf '%s\\n' ': # verified offline uv/uvx 0.9.7 already installed'\n"
        "    return 0\n"
        "  fi\n"
        "  command curl \"$@\"\n"
        "}\n"
        "export -f curl\n"
        "echo '[causalflow-infra] verifier uv/uvx 0.9.7 activated from original local cache'\n"
    )
    return archive, script


def _verifier_stage_setup(task_dir: Path) -> str:
    """Mirror BenchFlow's native verifier alias and task-owned environment."""

    import yaml

    text = (task_dir / "task.md").read_text()
    frontmatter = yaml.safe_load(text[4:].split("\n---\n", 1)[0])
    verifier_env = (frontmatter.get("verifier") or {}).get("env") or {}
    if not isinstance(verifier_env, dict):
        raise ValueError("task verifier.env must be a mapping")
    # BenchFlow _link_legacy_verifier_mount uses precisely this absent-only
    # alias.  Add it after replay; the root-owned /verifier stays unreadable
    # to agent, and any real /tests tree is preserved.
    lines = ["[ -e /tests ] || ln -s /verifier /tests"]
    for name, value in verifier_env.items():
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ValueError(f"invalid task verifier environment name: {name!r}")
        lines.append(f"export {name}={shlex.quote(os.path.expandvars(str(value)))}")
    return "\n".join(lines) + "\n"


def _run_branch(
    *,
    image: str,
    task_dir: Path,
    skills_root: Path,
    workspace: str,
    commands: list[str],
    timeout: int,
    command_timeouts: list[float] | None = None,
) -> dict[str, Any]:
    proxy_env: dict[str, str] = {}
    for name, value in container_proxy_env().items():
        proxy_env[name] = value
        # curl, uv, and apt do not agree on proxy-variable casing.  BenchFlow's
        # staged verifier exports both forms, so standalone replay must do the
        # same to preserve its network environment.
        proxy_env[name.lower()] = value
    resource_limits = _task_resource_limits(task_dir)
    verifier_uv_archive, verifier_setup = _cached_verifier_uv(task_dir)
    verifier_stage_setup = _verifier_stage_setup(task_dir)
    replay_mounts: list[str] = []
    replay_setup = ""
    if task_dir.name == "flink-query":
        from skillsbench_replay.maven_support import replay_mount_and_setup
        replay_mounts, replay_setup = replay_mount_and_setup(
            REPO_ROOT.parent / "infra-cache" / "maven" / task_dir.name
        )
    if task_dir.name in {'seismic-phase-picking', 'python-scala-translation'}:
        from skillsbench_replay.task_dependency_cache import replay_mount_and_setup
        replay_mounts, replay_setup = replay_mount_and_setup(
            REPO_ROOT.parent / 'infra-cache', task_dir.name
        )
    with tempfile.TemporaryDirectory(prefix="causalflow-sb-logs-") as logs_raw:
        logs = Path(logs_raw)
        # Docker's cidfile must remain readable by the host even while /logs
        # belongs to the non-root container agent (needed on timeout).
        logs.chmod(0o755)
        (logs / "verifier").mkdir(parents=True)
        verifier_copy = logs / "task-verifier"
        # BenchFlow uploads the verifier into a writable container directory.
        # Some official verifiers chmod helper scripts or create local cache
        # files.  Give every branch its own writable copy while preserving the
        # checked-out verifier tree byte-for-byte.
        shutil.copytree(task_dir / "verifier", verifier_copy)
        commands_path = logs / "replay-commands.json"
        executions_path = logs / "replay-executions.json"
        manifest_path = logs / "replay-manifest.json"
        identity_path = logs / "replay-identity.json"
        cid_path = logs / "container.cid"
        commands_path.write_text(json.dumps(commands, ensure_ascii=False))
        timeouts_option = ""
        if command_timeouts is not None:
            (logs / "replay-timeouts.json").write_text(json.dumps(command_timeouts))
            timeouts_option = "--command-timeouts /logs/replay-timeouts.json "
        script = (
            "set +e\n"
            + "restore_host_logs() { "
            + _host_log_permissions_script(os.getuid(), os.getgid())
            + "; }\n"
            + "trap restore_host_logs EXIT\n"
            + "python_bin=$(command -v python3 || command -v python)\n"
            + "if [ -z \"$python_bin\" ]; then echo 'python runtime not found' >&2; exit 127; fi\n"
            # BenchFlow creates a non-root `agent`, recursively transfers the
            # task workspace without changing its mode bits, and launches ACP
            # with HOME=/home/agent.  Reproduce that boundary here.  This is
            # material for tasks such as Suricata where `/root` is mode 0550:
            # the agent may edit existing files but may not create siblings.
            + "id -u agent >/dev/null 2>&1 || useradd -m -s /bin/bash agent\n"
            + "agent_uid=$(id -u agent)\n"
            + "agent_gid=$(id -g agent)\n"
            + "agent_home=/home/agent\n"
            + "mkdir -p \"$agent_home\"\n"
            + "if [ -d /root/.local/bin ] && [ ! -e \"$agent_home/.local/bin\" ]; then mkdir -p \"$agent_home/.local\"; ln -s /root/.local/bin \"$agent_home/.local/bin\"; fi\n"
            + "if [ -d /root/.nvm ] && [ ! -e \"$agent_home/.nvm\" ]; then ln -s /root/.nvm \"$agent_home/.nvm\"; fi\n"
            + f"chown -R agent:agent {shlex.quote(workspace)} 2>/dev/null || true\n"
            + "chown -R agent:agent \"$agent_home\" /logs 2>/dev/null || true\n"
            + "printf '{\"agent_user\":\"agent\",\"agent_uid\":%s,\"agent_gid\":%s,\"agent_home\":\"/home/agent\",\"verifier_user\":\"root\"}\\n' \"$agent_uid\" \"$agent_gid\" > "
            + shlex.quote("/logs/" + identity_path.name)
            + "\n"
            # Counterfactual commands must not be able to inspect verifier
            # source.  The root parent restores access when it invokes test.sh.
            + "chown -R root:root /verifier && chmod 700 /verifier\n"
            + ("chmod 700 /causalflow-verifier-support || exit 125\n"
               if verifier_uv_archive is not None else "")
            + replay_setup
            + "\"$python_bin\" /causalflow/skillsbench_replay/container_replay_driver.py "
            + f"--commands {shlex.quote('/logs/' + commands_path.name)} "
            + f"--workspace {shlex.quote(workspace)} "
            + f"--result {shlex.quote('/logs/' + executions_path.name)} "
            + f"--manifest {shlex.quote('/logs/' + manifest_path.name)} "
            + f"--command-timeout {max(1, min(timeout, 120))} "
            + timeouts_option
            + "--run-uid \"$agent_uid\" --run-gid \"$agent_gid\" --run-home \"$agent_home\"\n"
            + "driver_status=$?\n"
            + verifier_stage_setup
            + verifier_setup
            + "bash /verifier/test.sh\n"
            + "verifier_status=$?\n"
            + "exit $verifier_status\n"
        )
        command = [
            "docker",
            "run",
            "--rm",
            "--cpus",
            str(resource_limits["cpus"]),
            "--memory",
            f"{resource_limits['memory_mb']}m",
            "--cidfile",
            str(cid_path),
            "-v",
            f"{verifier_copy}:/verifier",
            "-v",
            f"{skills_root}:/skills:ro",
            # BenchFlow's with-skill image injection exposes the same tree at
            # agent discovery paths as well as /skills.  Recorded commands
            # may therefore use the canonical Claude-compatible path printed
            # inside a task's SKILL.md.  Mirror that read-only view so replay
            # matches the official rollout environment byte-for-byte.
            "-v",
            f"{skills_root}:/root/.claude/skills:ro",
            "-v",
            f"{logs}:/logs",
            "-v",
            f"{REPO_ROOT}:/causalflow:ro",
            "-w",
            workspace,
        ]
        for name, value in proxy_env.items():
            command.extend(["-e", f"{name}={value}"])
        if verifier_uv_archive is not None:
            command.extend([
                "-v", f"{verifier_uv_archive}:/causalflow-verifier-support/uv.tar.gz:ro",
            ])
        command.extend(replay_mounts)
        command.extend([image, "/bin/bash", "-lc", script])
        started = time.perf_counter()
        timed_out = False
        cleanup_log = ""
        try:
            result = subprocess.run(
                command,
                text=True,
                capture_output=True,
                check=False,
                timeout=timeout,
            )
            return_code = result.returncode
            stdout = result.stdout
            stderr = result.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            return_code = None
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode(errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode(errors="replace")
            container_id = (
                cid_path.read_text(errors="replace").strip()
                if cid_path.exists()
                else ""
            )
            if container_id:
                cleanup = subprocess.run(
                    ["docker", "rm", "-f", container_id],
                    text=True,
                    capture_output=True,
                    check=False,
                    timeout=30,
                )
                cleanup_log = cleanup.stdout + "\n" + cleanup.stderr
            stderr += f"\nbranch timed out after {timeout} seconds"
        finally:
            # SIGKILL/docker rm bypass the shell trap.  Recover only this
            # branch's temporary logs before reading or deleting them.
            _recover_host_log_permissions(logs, image, force=timed_out)
        elapsed = time.perf_counter() - started
        command_executions = (
            json.loads(executions_path.read_text())
            if executions_path.exists()
            else []
        )
        workspace_manifest = (
            json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
        )
        execution_identity = (
            json.loads(identity_path.read_text()) if identity_path.exists() else None
        )
        return {
            "reward": _read_reward(logs),
            "ctrf": _ctrf_counts(logs),
            "seconds": elapsed,
            "return_code": return_code,
            "timed_out": timed_out,
            "command_executions": command_executions,
            "workspace_manifest": workspace_manifest,
            "execution_identity": execution_identity,
            "resource_limits": resource_limits,
            "log_tail": (stdout + "\n" + stderr + "\n" + cleanup_log)[-12_000:],
        }


def _graph_step_dependencies(graph, target_step: int) -> tuple[list[int], list[int]]:
    """Return replayable ancestor and downstream steps for one branch point."""

    reverse: dict[str, list[str]] = {}
    forward: dict[str, list[str]] = {}
    for edge in graph.edges:
        reverse.setdefault(edge.target, []).append(edge.source)
        forward.setdefault(edge.source, []).append(edge.target)

    target_node = step_node_id(target_step)

    def reachable(start: str, adjacency: dict[str, list[str]]) -> set[str]:
        seen: set[str] = set()
        stack = list(adjacency.get(start, []))
        while stack:
            node_id = stack.pop()
            if node_id in seen:
                continue
            seen.add(node_id)
            stack.extend(adjacency.get(node_id, []))
        return seen

    ancestors = reachable(target_node, reverse)
    descendants = reachable(target_node, forward)

    def steps(node_ids: set[str], *, before: bool) -> list[int]:
        values = []
        for node_id in node_ids:
            node = graph.nodes.get(node_id)
            if not node or node.kind != NodeKind.STEP or node.step_id is None:
                continue
            if before and node.step_id < target_step:
                values.append(node.step_id)
            if not before and node.step_id > target_step:
                values.append(node.step_id)
        return sorted(set(values))

    return steps(ancestors, before=True), steps(descendants, before=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--task-dir", type=Path, required=True)
    parser.add_argument(
        "--repair-model",
        default=os.environ.get(
            "CAUSALFLOW_REPAIR_MODEL", "anthropic/claude-opus-4.7"
        ),
    )
    parser.add_argument("--proposals", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--image")
    parser.add_argument("--stop-on-success", action="store_true")
    parser.add_argument(
        "--proposal-mode",
        choices=("independent", "adaptive"),
        default="adaptive",
        help=(
            "Whether later candidates are sampled independently or may see "
            "earlier candidate diagnoses and official evaluation outcomes"
        ),
    )
    parser.add_argument(
        "--verifier-feedback",
        choices=("full", "none"),
        default="full",
        help="Whether the repair model may see stdout/stderr from the failed verifier",
    )
    args = parser.parse_args()
    if args.proposals < 1:
        raise SystemExit("--proposals must be positive")

    run_dir = args.run_dir.resolve()
    task_dir = args.task_dir.resolve()
    task_name = _safe_name(task_dir.name, "task name")
    parsed = load_run(run_dir)
    if parsed.reward is None:
        raise SystemExit("baseline run has no official reward")
    if parsed.reward >= 1.0:
        raise SystemExit("baseline already passes; no repair is needed")
    truncated = [
        event.step_id
        for event in parsed.events
        if event.kind == "execute" and not event.replayable
    ]
    if truncated:
        raise SystemExit(
            "baseline contains command calls without lossless replay evidence; "
            f"rerun the original rollout first (steps={truncated})"
        )

    verifier_paths = infer_verifier_reads(task_dir / "verifier")
    target = _target_event(parsed, verifier_paths)
    if not target.command:
        raise SystemExit("target event has no executable command")
    graph = SkillsBenchGraphBuilder().build(
        parsed.events,
        verifier_reads=verifier_paths,
        workspace_root=infer_task_workspace(task_dir),
    )
    target_writes = tuple(
        dict.fromkeys((*target.observed_writes, *target.inferred_writes))
    )
    changed_ids = resource_ids_for_paths(graph, target_writes)
    selection = ReplayPlanner().plan(graph, changed_ids) if changed_ids else None
    prerequisite_steps, downstream_steps = _graph_step_dependencies(
        graph, target.step_id
    )

    image = args.image or f"causalflow-skillsbench-{task_name}:repair"
    build = _build_image(task_dir, image, args.timeout)
    skills_root = task_dir / "environment" / "skills"
    workspace = infer_task_workspace(task_dir)
    commands = [materialize_replay_command(event) for event in parsed.events if event.command]
    target_index = next(
        index
        for index, event in enumerate(parsed.events)
        if event.step_id == target.step_id
    )
    prefix = [
        event.command
        for event in parsed.events[:target_index]
        if event.command
    ]
    suffix = [
        event.command
        for event in parsed.events[target_index + 1 :]
        if event.command
    ]
    causal_prerequisites = [
        event.command
        for event in parsed.events
        if event.step_id in prerequisite_steps and event.command
    ]
    causal_downstream = [
        event.command
        for event in parsed.events
        if event.step_id in downstream_steps and event.command
    ]

    print(f"replaying baseline task={task_name} commands={len(commands)}", flush=True)
    replay = _run_branch(
        image=image,
        task_dir=task_dir,
        skills_root=skills_root,
        workspace=workspace,
        commands=commands,
        timeout=args.timeout,
    )
    saved_baseline_ctrf = _ctrf_counts(run_dir)
    fidelity_report = _replay_fidelity_report(parsed, replay)
    replay_fidelity = replay["reward"] == parsed.reward and (
        saved_baseline_ctrf is None or replay["ctrf"] == saved_baseline_ctrf
    ) and all(
        fidelity_report[key]
        for key in (
            "lossless_command_markers",
            "command_count_matches",
            "return_codes_match",
            "artifact_hashes_match",
            "sandbox_identity_matches",
        )
    )
    if not replay_fidelity:
        raise SystemExit(
            "fresh replay does not reproduce the saved baseline: "
            f"saved_reward={parsed.reward} fresh_reward={replay['reward']} "
            f"saved_ctrf={saved_baseline_ctrf} fresh_ctrf={replay['ctrf']} "
            f"fidelity={json.dumps(fidelity_report, ensure_ascii=False)}"
        )
    api_key, key_source = load_key()
    task_text = (task_dir / "task.md").read_text(errors="replace")
    skills_text = _read_skills(skills_root)
    feedback = (
        _verifier_feedback(run_dir)
        if args.verifier_feedback == "full"
        else "[withheld for no-verifier-feedback ablation]"
    )
    candidates: list[dict[str, Any]] = []
    repair_payloads: list[dict[str, Any]] = []
    for proposal_index in range(args.proposals):
        prompt = _repair_prompt(
            task_text=task_text,
            skills_text=skills_text,
            target_step=target.step_id,
            original_command=target.command,
            original_output=target.output,
            verifier_feedback=feedback,
            trace_context=_trace_context(parsed, target.step_id),
            earlier_repairs=(
                repair_payloads if args.proposal_mode == "adaptive" else []
            ),
        )
        repair, call = _call_repair_model(
            model=args.repair_model,
            api_key=api_key,
            prompt=prompt,
        )
        repair_payloads.append(repair)
        print(
            f"evaluating proposal={proposal_index} diagnosis={repair.get('diagnosis', '')[:120]}",
            flush=True,
        )
        evaluation = _run_branch(
            image=image,
            task_dir=task_dir,
            skills_root=skills_root,
            workspace=workspace,
            commands=[
                *causal_prerequisites,
                repair["repaired_command"],
                *causal_downstream,
            ],
            timeout=args.timeout,
        )
        policy_line = next(
            (
                line.strip()
                for line in reversed(evaluation["log_tail"].splitlines())
                if "Policy-ladder reward:" in line
            ),
            "",
        )
        repair["_evaluation_feedback"] = {
            "reward": evaluation["reward"],
            "verifier_summary": policy_line,
        }
        candidates.append(
            {
                "proposal_index": proposal_index,
                "repair": repair,
                "model_call": call,
                "evaluation": evaluation,
            }
        )
        print(
            f"proposal={proposal_index} reward={evaluation['reward']} ctrf={evaluation['ctrf']}",
            flush=True,
        )
        if args.stop_on_success and evaluation["reward"] == 1.0:
            break

    best_reward = max(
        (item["evaluation"]["reward"] for item in candidates if item["evaluation"]["reward"] is not None),
        default=None,
    )
    result = {
        "experiment": "CausalFlow local command repair on SkillsBench",
        "task": task_name,
        "baseline_run": str(run_dir),
        "baseline_official_reward": parsed.reward,
        "baseline_saved_ctrf": saved_baseline_ctrf,
        "baseline_fresh_replay": replay,
        "baseline_replay_fidelity": fidelity_report,
        "repair_model": args.repair_model,
        "proposal_mode": args.proposal_mode,
        "repair_key_source": key_source,
        "evidence_policy": {
            "shown_to_repair_model": [
                "task.md",
                "deployed SKILL.md files",
                "target command and its output",
                *(
                    ["verifier stdout/stderr from failed rollout"]
                    if args.verifier_feedback == "full"
                    else []
                ),
            ],
            "not_shown_to_repair_model": [
                "verifier source",
                "expected-answer files",
                *(
                    ["verifier stdout/stderr from failed rollout"]
                    if args.verifier_feedback == "none"
                    else []
                ),
            ],
            "verifier_feedback_mode": args.verifier_feedback,
        },
        "target": {
            "step_id": target.step_id,
            "writes": list(target_writes),
            "verifier_paths": list(verifier_paths),
            "selection_from_target_outputs": selection.to_dict() if selection else None,
            "original_command": target.command,
        },
        "build": build,
        "candidates": candidates,
        "summary": {
            "proposals_evaluated": len(candidates),
            "best_reward": best_reward,
            "absolute_reward_gain": (
                best_reward - parsed.reward if best_reward is not None else None
            ),
            "full_repair_success": best_reward == 1.0,
            "fresh_replay_matches_saved_baseline": replay_fidelity,
            "fresh_replay_reward_matches_saved_baseline": (
                replay["reward"] == parsed.reward
            ),
            "causal_intervention_supported": (
                best_reward is not None and best_reward > parsed.reward
            ),
            "prefix_commands": len(prefix),
            "suffix_commands": len(suffix),
            "causal_prerequisite_steps": prerequisite_steps,
            "causal_downstream_steps": downstream_steps,
            "causal_replay_command_count": (
                len(causal_prerequisites) + 1 + len(causal_downstream)
            ),
            "commands_avoided_vs_full_trace": (
                len(commands)
                - len(causal_prerequisites)
                - 1
                - len(causal_downstream)
            ),
            "commands_regenerated": 1,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"output={args.output.resolve()}", flush=True)
    return 0 if best_reward is not None and best_reward > parsed.reward else 1


if __name__ == "__main__":
    raise SystemExit(main())
