#!/usr/bin/env python3
"""Run, resume, and audit the 22 repaired and 33 control rollouts."""

from __future__ import annotations

import argparse
import fcntl
import functools
import gzip
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterator


ROOT = Path("/Users/king/Documents/Codex/2026-11-18/skilltta-controlled-gpt52")
STABLE_ROOT = Path("/Users/king/Library/Application Support/SkillTTA/controlled-gpt52")
ACTIVE_EXECUTION = json.loads((STABLE_ROOT / "active-execution.json").read_text())
EVIDENCE_ROOT = STABLE_ROOT / "evidence/new"
STAGED_PREPARED_ROOT = STABLE_ROOT
PREPARED_ROOT = Path(ACTIVE_EXECUTION.get("prepared_root", str(STAGED_PREPARED_ROOT / "prepared")))
PREPARED_CONTROLS_ROOT = Path(ACTIVE_EXECUTION["prepared_controls_root"])
PACKAGE = Path(
    "/Users/king/Downloads/03_论文科研/skill-repair-controlled-datasets-20261020"
)
RUNNER = PACKAGE / "tools/runner.py"
BENCH = STABLE_ROOT / "runtimes/benchflow/bin/bench"
ENV_FILE = Path(
    "/Users/king/Documents/Codex/2026-09-20/"
    "https-github-com-xiaolin9595-workflow-localized/opus47-wml.env"
)
DOCKER_CONFIG = STABLE_ROOT / "docker-config"
BASE_URL = "https://maas.tatucloud.com/deployer/coding_tatu/v1"
REQUEST_MODEL = "gpt-5.2@AZUREOPENAI-default"
ROUTE_MODEL = "vllm/gpt-5.2@AZUREOPENAI-default"
DELIVERED_MODEL = "gpt-5.2-2025-12-11"
PROXY_RESPONSE_MODEL = "benchflow-vllm-gpt-5.2-AZUREOPENAI-default"
ALLOWED_RESPONSE_MODELS = {PROXY_RESPONSE_MODEL, REQUEST_MODEL}
LITELLM_EXECUTABLE = Path(
    str(STABLE_ROOT / "runtimes/litellm/bin/litellm")
)
BENCHFLOW_OVERLAY = STABLE_ROOT / "overlay"
REPAIR_METHOD = "skilltta-gpt52-tatumass-controlled22-20261118"
CONTROL_METHOD = "control-gpt52-tatumass-controlled33-20261118"
REASONING_EFFORT = "high"
PREBUILD_AUDIT = Path(ACTIVE_EXECUTION["environment_audit"])
EXECUTOR_RUNTIME_PREFLIGHT = Path(ACTIVE_EXECUTION["runtime_preflight"])
PROVIDER_PREFLIGHT = STABLE_ROOT / "audits/execution_provider_preflight.json"


def closed_attempt_snapshot(path: Path) -> bytes | None:
    """Use only checksum-verified snapshots of completed, immutable attempt files."""
    try:
        parts = path.relative_to(ROOT).parts
        if len(parts) < 5 or parts[0] != "runs" or not parts[3].startswith("attempt-"):
            return None
        cached_attempt = EVIDENCE_ROOT.joinpath(*parts[:4])
        manifest_path = cached_attempt / "LOCAL_EVIDENCE_SHA256.json"
        record_path = cached_attempt / "RUN_RECORD.json"
        if not manifest_path.is_file() or not record_path.is_file():
            return None
        manifest = json.loads(manifest_path.read_bytes())
        record = json.loads(record_path.read_bytes())
        if not record.get("finished_at") or record.get("bench_exit_code") is None:
            return None
        if manifest.get("source") != str(ROOT.joinpath(*parts[:4])):
            return None
        relative = "/".join(parts[4:])
        expected = manifest.get("files", {}).get(relative)
        snapshot = cached_attempt.joinpath(*parts[4:])
        if not expected or not snapshot.is_file():
            return None
        payload = snapshot.read_bytes()
        if hashlib.sha256(payload).hexdigest() != expected:
            raise RuntimeError("Closed-attempt snapshot checksum mismatch: " + str(path))
        return payload
    except (ValueError, OSError):
        return None


def read_json(path: Path) -> dict[str, Any]:
    snapshot = closed_attempt_snapshot(path)
    if snapshot is not None:
        value = json.loads(snapshot)
        if not isinstance(value, dict):
            raise ValueError("Expected JSON object: " + str(path))
        return value
    last_error: OSError | None = None
    for delay in (0, 1, 2, 4, 8):
        if delay:
            time.sleep(delay)
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            break
        except OSError as exc:
            last_error = exc
    else:
        assert last_error is not None
        raise last_error
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


@functools.lru_cache(maxsize=1)
def read_api_key() -> str:
    values: dict[str, str] = {}
    env_text = None
    for delay in (0, 2, 4, 8, 16, 30):
        if delay:
            time.sleep(delay)
        try:
            env_text = ENV_FILE.read_text(encoding="utf-8")
            break
        except OSError:
            if delay == 30:
                raise
    if env_text is None:
        raise RuntimeError("Credential file could not be read")
    for line in env_text.splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    api_key = values.get("WML_API_KEY", "")
    if not api_key:
        raise RuntimeError("WML_API_KEY is missing")
    return api_key


def execution_env() -> dict[str, str]:
    api_key = read_api_key()
    env = os.environ.copy()
    overlay = str(BENCHFLOW_OVERLAY)
    pythonpath_entries = [
        entry
        for entry in env.get("PYTHONPATH", "").split(os.pathsep)
        if entry and entry != overlay
    ]
    env.update(
        {
            "OPENAI_API_KEY": api_key,
            "BENCHFLOW_PROVIDER_API_KEY": api_key,
            "BENCHFLOW_PROVIDER_BASE_URL": BASE_URL,
            "BENCHFLOW_PROVIDER_PROTOCOL": "openai-completions",
            "BENCHFLOW_PROVIDER_REASONING_EFFORT": REASONING_EFFORT,
            "BENCHFLOW_REASONING_EFFORT": REASONING_EFFORT,
            "BENCHFLOW_TASK_WALL_TIMEOUT_SEC": "21600",
            "BENCHFLOW_TASK_IDLE_TIMEOUT_SEC": "3600",
            "BENCHFLOW_LLM_REQUEST_TIMEOUT_SEC": "3600",
            "BENCHFLOW_ACP_HANDSHAKE_TIMEOUT": "300",
            "BENCHFLOW_AGENT_INSTALL_TIMEOUT_SEC": "2400",
            "BENCHFLOW_LITELLM_ROUTER_NUM_RETRIES": "5",
            "BENCHFLOW_LITELLM_HEALTH_TIMEOUT_SEC": "600",
            "BENCHFLOW_LITELLM_EXECUTABLE": str(LITELLM_EXECUTABLE),
            "LITELLM_LOCAL_MODEL_COST_MAP": "True",
            "PYTHONPYCACHEPREFIX": str(STABLE_ROOT / "pycache"),
            "TIKTOKEN_CACHE_DIR": str(STABLE_ROOT / "tokenizer-cache"),
            "NO_PROXY": "localhost,127.0.0.1,::1,host.docker.internal,main",
            "no_proxy": "localhost,127.0.0.1,::1,host.docker.internal,main",
            "DOCKER_HOST": "unix:///Users/king/.docker/run/docker.sock",
            "DOCKER_BUILDKIT": "1",
            "DOCKER_CONFIG": str(DOCKER_CONFIG),
            "PYTHONPATH": os.pathsep.join([overlay, *pythonpath_entries]),
        }
    )
    for name in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "BUILDX_BUILDER",
        "DOCKER_CONTEXT",
    ):
        env.pop(name, None)
    return env


def require_prebuilt_environments() -> None:
    if not PREBUILD_AUDIT.is_file():
        raise RuntimeError("Run tools/prebuild_environments.py before formal rollouts")
    audit = read_json(PREBUILD_AUDIT)
    records = audit.get("records")
    if not isinstance(records, list) or len(records) != 55:
        raise RuntimeError("Environment prebuild audit does not cover 55 prepared bundles")
    expected: dict[tuple[str, str], str] = {}
    for kind, directory in (
        ("repaired", PREPARED_ROOT),
        ("control", PREPARED_CONTROLS_ROOT),
    ):
        for prepared in directory.iterdir():
            if prepared.is_dir():
                expected[(kind, prepared.name)] = hashlib.sha256(
                    (prepared / "PREPARED_SHA256.json").read_bytes()
                ).hexdigest()
    actual = {
        (record.get("kind"), record.get("prepared_id")): record.get(
            "prepared_manifest_sha256"
        )
        for record in records
        if isinstance(record, dict) and record.get("passed") is True
    }
    if audit.get("passed") is not True or actual != expected:
        raise RuntimeError("Environment prebuild audit is incomplete or stale")
    if (audit.get("freeze") or {}).get("passed") is not True:
        raise RuntimeError("Final environment freeze has not passed")
    inspect_env = os.environ.copy()
    inspect_env["DOCKER_HOST"] = "unix:///Users/king/.docker/run/docker.sock"
    inspect_env["DOCKER_CONFIG"] = str(DOCKER_CONFIG)
    inspect_env.pop("DOCKER_CONTEXT", None)
    verified_images: set[str] = set()
    for record in records:
        image = record["image"]
        if image in verified_images:
            continue
        identity = (record.get("build") or {}).get("image_id")
        result = subprocess.run(
            ["docker", "image", "inspect", image, "--format", "{{.Id}}"],
            capture_output=True, text=True, env=inspect_env, timeout=30,
        )
        if not identity or result.returncode or result.stdout.strip() != identity:
            raise RuntimeError("Frozen environment image identity changed: " + image)
        verified_images.add(image)


def require_executor_runtime() -> None:
    if not EXECUTOR_RUNTIME_PREFLIGHT.is_file():
        raise RuntimeError("Run tools/preflight_executor_runtime.py before formal rollouts")
    audit = read_json(EXECUTOR_RUNTIME_PREFLIGHT)
    if audit.get("passed") is not True or audit.get("consecutive_imports") != 5:
        raise RuntimeError("Executor runtime preflight did not pass")
    expected = audit.get("bench_sha256")
    actual = hashlib.sha256(BENCH.read_bytes()).hexdigest()
    if expected != actual:
        raise RuntimeError("Executor runtime preflight is stale")
    proxy = audit.get("proxy") or {}
    if (proxy.get("passed") is not True or proxy.get("consecutive_imports") != 5
            or len(proxy.get("health_boots", [])) != 2
            or not all(item.get("healthy") for item in proxy["health_boots"])):
        raise RuntimeError("Independent proxy runtime checks have not passed")
    for name, expected_hash in audit.get("critical_files", {}).items():
        path = Path(name)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
            raise RuntimeError("A checked runtime asset changed: " + name)
    checked_env = os.environ.copy()
    checked_env["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
    checked_env["PYTHONPYCACHEPREFIX"] = str(STABLE_ROOT / "pycache")
    check = subprocess.run(
        [str(STABLE_ROOT / "runtimes/litellm/bin/python"), "-I", "-c",
         "import litellm,litellm.proxy.proxy_server"],
        env=checked_env, capture_output=True, timeout=90,
    )
    if check.returncode:
        raise RuntimeError("Proxy dependency guard failed before creating a model attempt")


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    yield value


def task_result_files(attempt: Path) -> list[Path]:
    files: list[Path] = []
    for path in (attempt / "jobs").rglob("result.json"):
        value = read_json(path)
        if "task_name" in value or "rewards" in value or "verifier_result" in value:
            files.append(path)
    return files


def trajectory_path(job: Path, stem: str) -> Path | None:
    plain = job / f"trajectory/{stem}.jsonl"
    compressed = plain.with_suffix(plain.suffix + ".gz")
    if plain.is_file():
        return plain
    if compressed.is_file():
        return compressed
    return None


def provider_audit(path: Path) -> dict[str, Any]:
    records = list(iter_jsonl(path))
    successes = 0
    failures = 0
    response_models: set[str] = set()
    provider_models: set[str] = set()
    request_models: set[str] = set()
    reasoning_efforts: set[str] = set()
    for record in records:
        response = record.get("response") or {}
        if response.get("status_code") == 200:
            successes += 1
        else:
            failures += 1
        body = response.get("body") or {}
        if isinstance(body, dict) and isinstance(body.get("model"), str):
            response_models.add(body["model"])
        metadata = record.get("metadata") or {}
        if isinstance(metadata.get("provider_model"), str):
            provider_models.add(metadata["provider_model"])
        request = record.get("request") or {}
        request_body = request.get("body") or {}
        if isinstance(request_body, dict):
            if isinstance(request_body.get("model"), str):
                request_models.add(request_body["model"])
            if isinstance(request_body.get("reasoning_effort"), str):
                reasoning_efforts.add(request_body["reasoning_effort"])
    return {
        "records": len(records),
        "successes": successes,
        "transport_failures": failures,
        "response_models": sorted(response_models),
        "provider_models": sorted(provider_models),
        "request_models": sorted(request_models),
        "reasoning_efforts": sorted(reasoning_efforts),
    }


def credential_leaks(root: Path, needle: bytes) -> list[str]:
    leaks: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        opener = gzip.open if path.suffix == ".gz" else open
        overlap = b""
        try:
            with opener(path, "rb") as handle:
                while chunk := handle.read(8 * 1024 * 1024):
                    value = overlap + chunk
                    if needle in value:
                        leaks.append(path.relative_to(root).as_posix())
                        break
                    overlap = value[-max(0, len(needle) - 1) :]
        except (OSError, EOFError):
            continue
    return leaks


def audit_attempt(attempt: Path) -> dict[str, Any]:
    audit: dict[str, Any] = {
        "schema_version": 3,
        "request_model": REQUEST_MODEL,
        "execution_route_model": ROUTE_MODEL,
        "expected_delivered_model": DELIVERED_MODEL,
        "provider_base_url": BASE_URL,
        "reasoning_effort": REASONING_EFFORT,
        "valid": False,
    }
    record_path = attempt / "RUN_RECORD.json"
    if not record_path.is_file():
        audit["invalid_reason"] = "missing_run_record"
        return audit
    record = read_json(record_path)
    if record.get("bench_exit_code") != 0:
        audit["invalid_reason"] = "bench_exit_nonzero"
        audit["bench_exit_code"] = record.get("bench_exit_code")
        return audit
    result_files = task_result_files(attempt)
    usable_results: list[tuple[Path, dict[str, Any]]] = []
    for candidate in result_files:
        candidate_result = read_json(candidate)
        if any(
            candidate_result.get(key)
            for key in (
                "error",
                "verifier_error",
                "exception_info",
                "exception",
                "error_message",
                "partial_trajectory",
            )
        ):
            continue
        candidate_rewards = candidate_result.get("rewards") or (
            candidate_result.get("verifier_result") or {}
        ).get("rewards", {})
        candidate_reward = (
            candidate_rewards.get("reward")
            if isinstance(candidate_rewards, dict)
            else None
        )
        if isinstance(candidate_reward, bool):
            candidate_reward = float(candidate_reward)
        if isinstance(candidate_reward, (int, float)) and 0 <= candidate_reward <= 1:
            usable_results.append((candidate, candidate_result))
    if len(usable_results) != 1:
        audit["invalid_reason"] = "result_count"
        audit["result_count"] = len(result_files)
        audit["usable_result_count"] = len(usable_results)
        return audit
    result_path, result = usable_results[0]
    if any(
        result.get(key)
        for key in (
            "error",
            "verifier_error",
            "exception_info",
            "exception",
            "error_message",
            "partial_trajectory",
        )
    ):
        audit["invalid_reason"] = "execution_or_verifier_error"
        return audit
    verifier_log = result_path.parent / "verifier/test-stdout.txt"
    cached_verifier = closed_attempt_snapshot(verifier_log)
    verifier_text = cached_verifier.decode("utf-8", errors="replace") if cached_verifier is not None else (verifier_log.read_text(encoding="utf-8", errors="replace") if verifier_log.is_file() else "")
    # Scores are usable only after the actual pytest process starts; installation
    # scripts can otherwise synthesize reward=0 after an infrastructure failure.
    if "test session starts" not in verifier_text:
        audit["invalid_reason"] = "verifier_tests_not_started"
        audit["verifier_log_sha256"] = hashlib.sha256(verifier_text.encode()).hexdigest()
        return audit
    report_path = result_path.parent / "verifier/ctrf.json"
    report = read_json(report_path) if report_path.is_file() else {}
    test_summary = (report.get("results") or {}).get("summary") or {}
    if (test_summary.get("tests", 0) <= 0 or
            test_summary.get("passed", 0) + test_summary.get("failed", 0) <= 0 or
            "error during collection" in verifier_text or "errors during collection" in verifier_text):
        audit["invalid_reason"] = "verifier_collection_failed_or_no_tests_executed"
        return audit
    rewards = result.get("rewards") or (result.get("verifier_result") or {}).get(
        "rewards", {}
    )
    reward = rewards.get("reward") if isinstance(rewards, dict) else None
    if isinstance(reward, bool):
        reward = float(reward)
    if not isinstance(reward, (int, float)) or not 0 <= reward <= 1:
        audit["invalid_reason"] = "missing_reward"
        return audit
    job = result_path.parent
    acp = trajectory_path(job, "acp_trajectory")
    llm = trajectory_path(job, "llm_trajectory")
    if acp is None or llm is None:
        audit["invalid_reason"] = "missing_trajectory"
        audit["acp_present"] = acp is not None
        audit["llm_present"] = llm is not None
        return audit
    acp_records = sum(1 for _ in iter_jsonl(acp))
    provider = provider_audit(llm)
    if acp_records == 0 or provider["successes"] == 0:
        audit["invalid_reason"] = "empty_trajectory"
        return audit
    preflight_path = PROVIDER_PREFLIGHT
    preflight = read_json(preflight_path) if preflight_path.is_file() else {}
    model_contract_ok = (
        preflight.get("passed") is True
        and preflight.get("request_model") == REQUEST_MODEL
        and preflight.get("delivered_model") == DELIVERED_MODEL
        and preflight.get("reasoning_effort") == REASONING_EFFORT
        and set(provider["request_models"]) == {REQUEST_MODEL}
        and set(provider["reasoning_efforts"]) == {REASONING_EFFORT}
        and bool(provider["response_models"])
        and set(provider["response_models"]).issubset(ALLOWED_RESPONSE_MODELS)
    )
    if not model_contract_ok:
        audit["invalid_reason"] = "model_or_reasoning_contract_mismatch"
        audit["provider"] = provider
        audit["provider_preflight"] = preflight
        return audit
    leaks = credential_leaks(attempt, read_api_key().encode())
    if leaks:
        audit["invalid_reason"] = "credential_leak"
        audit["credential_leak_files"] = leaks
        return audit
    audit.update(
        {
            "valid": True,
            "status": "pass" if reward == 1 else "fail",
            "reward": reward,
            "result_file": result_path.relative_to(attempt).as_posix(),
            "acp_records": acp_records,
            "provider": provider,
            "provider_preflight_sha256": hashlib.sha256(
                preflight_path.read_bytes()
            ).hexdigest(),
            "credential_leaks": 0,
        }
    )
    return audit


def attempt_prepared_sha256(attempt: Path) -> str | None:
    record_path = attempt / "RUN_RECORD.json"
    if not record_path.is_file():
        audit_path = attempt / "EXECUTION_AUDIT.json"
        if not audit_path.is_file():
            return None
        value = read_json(audit_path).get("prepared_manifest_sha256")
        return value if isinstance(value, str) else None
    value = read_json(record_path).get("prepared_sha256")
    return value if isinstance(value, str) else None


def counts_as_infrastructure_attempt(attempt: Path, prepared_sha256: str) -> bool:
    if attempt_prepared_sha256(attempt) != prepared_sha256:
        return False
    audit_path = attempt / "EXECUTION_AUDIT.json"
    if audit_path.is_file():
        audit = read_json(audit_path)
        if audit.get("invalid_reason") == "manual_prebuild_transition":
            return False
    return True


def completed_attempt(
    run_root: Path, prepared_sha256: str
) -> tuple[Path, dict[str, Any]] | None:
    for attempt in sorted(run_root.glob("attempt-*")):
        if not (attempt / "RUN_RECORD.json").is_file():
            continue
        if attempt_prepared_sha256(attempt) != prepared_sha256:
            continue
        audit_path = attempt / "EXECUTION_AUDIT.json"
        cached_attempt = EVIDENCE_ROOT / attempt.relative_to(ROOT)
        audit_source = cached_attempt if (cached_attempt / "LOCAL_EVIDENCE_SHA256.json").is_file() else attempt
        if audit_path.is_file():
            audit = read_json(audit_path)
            if audit.get("schema_version") != 3:
                audit = audit_attempt(audit_source)
        else:
            audit = audit_attempt(audit_source)
            write_json(audit_path, audit)
        if (
            audit.get("valid") is True
            and attempt_prepared_sha256(attempt) == prepared_sha256
        ):
            return attempt, audit
    return None


def next_attempt(run_root: Path) -> Path:
    numbers: list[int] = []
    for path in run_root.glob("attempt-*"):
        try:
            numbers.append(int(path.name.split("-")[-1]))
        except ValueError:
            pass
    return run_root / f"attempt-{max(numbers, default=0) + 1:03d}"


def control_plan() -> list[dict[str, Any]]:
    plan = read_json(STABLE_ROOT / "control-plan.json")
    rows = plan.get("controls")
    if not isinstance(rows, list) or len(rows) != 33:
        raise RuntimeError("Expected a prepared 33-row control plan")
    return rows


def repaired_plan() -> list[dict[str, Any]]:
    catalog = read_json(PACKAGE / "datasets/catalog.json")
    rows = catalog.get("trials")
    if not isinstance(rows, list) or len(rows) != 22:
        raise RuntimeError("Expected 22 catalog trials")
    return sorted(rows, key=lambda row: (row["task_id"] == "data-to-d3", row["trial_id"]))


def execute_one(
    *,
    prepared: Path,
    run_root: Path,
    method: str,
    repair_model: str | None,
    env: dict[str, str],
) -> tuple[Path, dict[str, Any]]:
    require_executor_runtime()
    prepared_sha256 = hashlib.sha256(
        (prepared / "PREPARED_SHA256.json").read_bytes()
    ).hexdigest()
    existing = completed_attempt(run_root, prepared_sha256)
    if existing is not None:
        return existing
    revision_attempts = sum(
        counts_as_infrastructure_attempt(attempt, prepared_sha256)
        for attempt in run_root.glob("attempt-*")
    )
    if revision_attempts >= 3:
        raise RuntimeError(
            f"No valid execution after three attempts for prepared revision: "
            f"{run_root.name} ({prepared_sha256})"
        )
    for retry in range(revision_attempts + 1, 4):
        attempt = next_attempt(run_root)
        command = [
            sys.executable,
            "-B",
            str(RUNNER),
            "eval",
            "--prepared",
            str(prepared),
            "--jobs",
            str(attempt),
            "--agent",
            "openhands",
            "--model",
            ROUTE_MODEL,
            "--method",
            method,
            "--bench",
            str(BENCH),
        ]
        if repair_model:
            command.extend(["--repair-model", repair_model])
        completed = subprocess.run(command, cwd=ROOT, env=env)
        audit = audit_attempt(attempt)
        audit["runner_exit_code"] = completed.returncode
        audit["infrastructure_attempt_number"] = retry
        audit["prepared_manifest_sha256"] = prepared_sha256
        write_json(attempt / "EXECUTION_AUDIT.json", audit)
        if audit.get("valid") is True:
            return attempt, audit
        print(
            json.dumps(
                {
                    "attempt": str(attempt),
                    "infrastructure_retry": retry,
                    "invalid_reason": audit.get("invalid_reason"),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    raise RuntimeError(f"No valid execution after three attempts: {run_root.name}")


def run_repaired(env: dict[str, str], start_at: str | None = None) -> None:
    rows = repaired_plan()
    trial_ids = [row["trial_id"] for row in rows]
    if start_at is not None and start_at not in trial_ids:
        raise ValueError("Unknown repaired resume ID: " + start_at)
    start_index = trial_ids.index(start_at) if start_at is not None else 0
    for ordinal, row in enumerate(rows, 1):
        if ordinal <= start_index:
            continue
        trial_id = row["trial_id"]
        attempt, audit = execute_one(
            prepared=PREPARED_ROOT / trial_id,
            run_root=ROOT / "runs/repaired" / trial_id,
            method=REPAIR_METHOD,
            repair_model=REQUEST_MODEL,
            env=env,
        )
        print(
            json.dumps(
                {
                    "kind": "repaired",
                    "done": ordinal,
                    "total": len(rows),
                    "trial_id": trial_id,
                    "attempt": attempt.name,
                    "status": audit["status"],
                    "reward": audit["reward"],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )


def run_controls(env: dict[str, str]) -> None:
    rows = control_plan()
    for ordinal, row in enumerate(rows, 1):
        control_id = row["control_id"]
        attempt, audit = execute_one(
            prepared=PREPARED_CONTROLS_ROOT / control_id,
            run_root=ROOT / "runs/controls" / control_id,
            method=CONTROL_METHOD,
            repair_model=None,
            env=env,
        )
        print(
            json.dumps(
                {
                    "kind": "control",
                    "done": ordinal,
                    "total": len(rows),
                    "control_id": control_id,
                    "attempt": attempt.name,
                    "status": audit["status"],
                    "reward": audit["reward"],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )


def collect(kind: str, output: str) -> None:
    path = ROOT / output
    if path.exists():
        path.unlink()
    subprocess.run(
        [
            sys.executable,
            "-B",
            str(RUNNER),
            "collect",
            "--runs",
            str(ROOT / "runs" / kind),
            "--out",
            str(path),
        ],
        cwd=ROOT,
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("repaired", "controls", "all"), default="all")
    parser.add_argument("--start-repaired-at", help="Resume a suffix without reading earlier iCloud metadata; earlier evidence still requires final audit")
    parser.add_argument("--defer-collection", action="store_true", help="Defer full historical evidence collection until file hydration completes")
    args = parser.parse_args()
    if not BENCH.is_file():
        raise FileNotFoundError(BENCH)
    require_executor_runtime()
    if not LITELLM_EXECUTABLE.is_file():
        raise FileNotFoundError(LITELLM_EXECUTABLE)
    if not (BENCHFLOW_OVERLAY / "benchflow/__init__.py").is_file():
        raise FileNotFoundError(BENCHFLOW_OVERLAY / "benchflow/__init__.py")
    if not (STABLE_ROOT / "audits/prepare_audit.json").is_file():
        raise RuntimeError("Run tools/prepare_evals.py first")
    require_prebuilt_environments()
    dependency_preflight = read_json(STABLE_ROOT / "audits/executor-package-visibility-v4.json")
    if (dependency_preflight.get("passed") is not True
            or dependency_preflight.get("prepared_root") != str(PREPARED_ROOT)
            or dependency_preflight.get("prepared_controls_root") != str(PREPARED_CONTROLS_ROOT)
            or dependency_preflight.get("environment_audit_sha256") != hashlib.sha256(PREBUILD_AUDIT.read_bytes()).hexdigest()):
        raise RuntimeError("Current task executor dependencies have not passed preflight")
    env = execution_env()
    pythonpath_entries = env["PYTHONPATH"].split(os.pathsep)
    if pythonpath_entries[0] != str(BENCHFLOW_OVERLAY):
        raise RuntimeError("BenchFlow overlay is not first on PYTHONPATH")
    if pythonpath_entries.count(str(BENCHFLOW_OVERLAY)) != 1:
        raise RuntimeError("BenchFlow overlay must occur exactly once on PYTHONPATH")
    with (ROOT / "evaluation.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.kind in ("repaired", "all"):
            run_repaired(env, args.start_repaired_at)
            if not args.defer_collection:
                collect("repaired", "results-summary.json")
        if args.kind in ("controls", "all"):
            run_controls(env)
            if not args.defer_collection:
                collect("controls", "control-results-summary.json")
    print(json.dumps({"runner_finished": True, "kind": args.kind,
                      "start_repaired_at": args.start_repaired_at,
                      "collection_deferred": args.defer_collection}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
