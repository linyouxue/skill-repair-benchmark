#!/usr/bin/env python3
"""Run prepared WML candidates with BenchFlow; retry infrastructure only."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import threading


ROOT = Path(os.environ.get("WML_CONTROLLED_ROOT", Path(__file__).resolve().parent.parent))
PREPARED = ROOT / "prepared"
RUNS = ROOT / "eval-runs"
RUNNER = Path(__file__).resolve().parent / "safe_controlled_eval.py"
BENCH_SHIM = Path(__file__).resolve().parent / "bench_paratera.sh"
ENV_FILE = Path(os.environ.get(
    "WML_CLAUDE_ENV_FILE",
    "/Users/king/Documents/Codex/2026-09-18/skillaxe-20-17-skillaxe-39-48-2/claudeapikey.env",
))
METHOD = "WML-Paratera-Claude47-Controlled-20261029"
MODEL = "paratera/Claude-Opus-4.7"
BASE_URL = os.environ.get("WML_BASE_URL", "https://llmapi.paratera.com")
LOCK = threading.Lock()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_key() -> str:
    for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip().removeprefix("export ").strip() == "API_KEY":
            return value.strip().strip('"').strip("'")
    raise RuntimeError("API_KEY not found")


def result_files(attempt: Path) -> list[Path]:
    return sorted(attempt.glob("jobs/*/*/result.json"))


def valid_result(attempt: Path) -> dict | None:
    audit_file = attempt / "EXECUTION_AUDIT.json"
    if not audit_file.is_file():
        return None
    try:
        audit = json.loads(audit_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if audit.get("valid") is not True:
        return None
    files = result_files(attempt)
    if len(files) != 1:
        return None
    try:
        data = json.loads(files[0].read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if any(data.get(key) for key in ("error", "verifier_error", "exception", "exception_info", "error_message")):
        return None
    if data.get("partial_trajectory") or data.get("execution_ok") is False:
        return None
    rewards = data.get("rewards")
    reward = rewards.get("reward") if isinstance(rewards, dict) else None
    if isinstance(reward, bool):
        reward = float(reward)
    if not isinstance(reward, (int, float)) or not 0 <= reward <= 1:
        return None
    return {"reward": float(reward), "result_file": str(files[0]), "valid": True}


def existing_valid(trial: str) -> dict | None:
    attempts = sorted(RUNS.glob(f"{trial}-attempt-*"))
    for attempt in reversed(attempts):
        result = valid_result(attempt)
        if result:
            return {**result, "attempt_dir": str(attempt)}
    return None


def next_attempt(trial: str) -> tuple[int, Path]:
    indexes = []
    for path in RUNS.glob(f"{trial}-attempt-*"):
        try:
            indexes.append(int(path.name.rsplit("-", 1)[1]))
        except ValueError:
            pass
    index = max(indexes, default=0) + 1
    return index, RUNS / f"{trial}-attempt-{index:03d}"


def run_trial(prepared: Path, key: str, retries: int) -> dict:
    trial = prepared.name
    old = existing_valid(trial)
    if old:
        return {"trial_id": trial, "status": "pass" if old["reward"] == 1 else "fail", **old, "new_attempts": 0}
    env = dict(os.environ)
    env.update({
        "PARATERA_API_KEY": key,
        "PARATERA_BASE_URL": BASE_URL,
        "NO_PROXY": "127.0.0.1,localhost,host.docker.internal",
        "no_proxy": "127.0.0.1,localhost,host.docker.internal",
    })
    failures = []
    for retry in range(1, retries + 1):
        index, attempt = next_attempt(trial)
        command = [
            sys.executable, str(RUNNER),
            "--prepared", str(prepared),
            "--jobs", str(attempt),
            "--agent", "openhands",
            "--model", MODEL,
            "--method", METHOD,
            "--repair-model", "Claude-Opus-4.7",
            "--bench", str(BENCH_SHIM),
        ]
        completed = subprocess.run(command, cwd=str(ROOT), env=env, capture_output=True, text=True)
        result = valid_result(attempt)
        if result:
            status = "pass" if result["reward"] == 1 else "fail"
            with LOCK:
                print(f"VALID {trial} status={status} reward={result['reward']:.3f} attempt={index}", flush=True)
            return {
                "trial_id": trial, "status": status, **result,
                "attempt_dir": str(attempt), "new_attempts": retry,
            }
        failures.append({
            "attempt": index,
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-1000:],
            "stderr_tail": completed.stderr[-1000:],
        })
        with LOCK:
            print(f"INVALID {trial} attempt={index}; retry={retry < retries}", flush=True)
    return {"trial_id": trial, "status": "invalid", "valid": False, "new_attempts": retries, "failures": failures}


def write_summary(rows: list[dict]) -> None:
    value = {
        "method": METHOD,
        "repair_model": "Claude-Opus-4.7",
        "executor_agent": "openhands",
        "executor_model": MODEL,
        "base_url": BASE_URL,
        "total": len(list(PREPARED.iterdir())),
        "valid": sum(row.get("valid") is True for row in rows),
        "passes": sum(row.get("status") == "pass" for row in rows),
        "failures": sum(row.get("status") == "fail" for row in rows),
        "invalid": sum(row.get("status") == "invalid" for row in rows),
        "trials": sorted(rows, key=lambda row: row["trial_id"]),
        "updated_at": now(),
    }
    temp = ROOT / "eval_summary.json.tmp"
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(ROOT / "eval_summary.json")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument(
        "--trials",
        nargs="*",
        help="Optional prepared trial IDs to run; existing valid attempts are still skipped.",
    )
    args = parser.parse_args()
    RUNS.mkdir(parents=True, exist_ok=True)
    key = load_key()
    rows: list[dict] = []
    selected = set(args.trials or ())
    prepared = sorted(
        path for path in PREPARED.iterdir()
        if path.is_dir() and (not selected or path.name in selected)
    )
    missing = selected.difference(path.name for path in prepared)
    if missing:
        parser.error(f"unknown trial IDs: {', '.join(sorted(missing))}")
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(run_trial, path, key, args.retries): path.name for path in prepared}
        for future in as_completed(futures):
            try:
                rows.append(future.result())
            except Exception as error:
                rows.append({"trial_id": futures[future], "status": "invalid", "valid": False, "error": repr(error)})
            write_summary(rows)
    write_summary(rows)
    return 1 if any(row.get("status") == "invalid" for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
