#!/usr/bin/env python3
"""Run every isolated controlled-dataset export through the WML adapter."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading


ROOT = Path(__file__).resolve().parent
INPUTS = ROOT / "inputs"
CANDIDATES = ROOT / "candidates"
FAILURES = ROOT / "failed-attempts"
ADAPTER = ROOT / "wml_adapter.py"
RUNNER = Path("/Users/king/Downloads/skill-repair-controlled-datasets-20261020/tools/runner.py")
ENV_FILE = Path("/Users/king/Documents/Codex/2026-09-18/skillaxe-20-17-skillaxe-39-48-2/claudeapikey.env")
LOCK = threading.Lock()


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_key() -> str:
    for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip().removeprefix("export ").strip() == "API_KEY":
            return value.strip().strip('"').strip("'")
    raise RuntimeError("API_KEY was not found")


def complete(path: Path) -> bool:
    if not (path / "response.json").is_file() or not (path / "CANDIDATE_SHA256.json").is_file():
        return False
    try:
        run = json.loads((path / "repair_run.json").read_text(encoding="utf-8"))
        return run.get("exit_code") == 0
    except (OSError, ValueError):
        return False


def archive_failure(trial: str, path: Path, attempt: int) -> None:
    if not path.exists():
        return
    FAILURES.mkdir(parents=True, exist_ok=True)
    target = FAILURES / f"{trial}-batch-attempt-{attempt:02d}"
    suffix = 1
    while target.exists():
        target = FAILURES / f"{trial}-batch-attempt-{attempt:02d}-{suffix}"
        suffix += 1
    shutil.move(str(path), str(target))


def run_trial(trial_dir: Path, api_key: str, retries: int) -> dict:
    trial = trial_dir.name
    output = CANDIDATES / trial
    if complete(output):
        return {"trial_id": trial, "status": "complete", "attempts": 0, "finished_at": timestamp()}
    env = dict(os.environ)
    env["API_KEY"] = api_key
    errors = []
    for attempt in range(1, retries + 1):
        archive_failure(trial, output, attempt)
        command = [
            sys.executable, str(RUNNER), "repair",
            "--input", str(trial_dir),
            "--out", str(output),
            "--adapter", sys.executable, str(ADAPTER),
        ]
        completed = subprocess.run(command, cwd=str(ROOT), env=env, capture_output=True, text=True)
        if completed.returncode == 0 and complete(output):
            response = json.loads((output / "response.json").read_text(encoding="utf-8"))
            with LOCK:
                print(f"COMPLETE {trial} changed={len(response.get('changed_files', []))} attempt={attempt}", flush=True)
            return {
                "trial_id": trial, "status": "complete", "attempts": attempt,
                "changed_files": response.get("changed_files", []), "finished_at": timestamp(),
            }
        errors.append({
            "attempt": attempt,
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-2000:],
            "stderr_tail": completed.stderr[-2000:],
        })
        with LOCK:
            print(f"RETRY {trial} after attempt={attempt}", flush=True)
    return {"trial_id": trial, "status": "failed", "attempts": retries, "errors": errors, "finished_at": timestamp()}


def write_summary(rows: list[dict]) -> None:
    value = {
        "method": "workflow-localized-mechanism-learning",
        "repair_model": "Claude-Opus-4.7",
        "provider": "Paratera",
        "base_url": "https://llmapi.paratera.com/v1",
        "total": len(list(INPUTS.iterdir())),
        "complete": sum(row.get("status") == "complete" for row in rows),
        "failed": sum(row.get("status") == "failed" for row in rows),
        "trials": sorted(rows, key=lambda row: row["trial_id"]),
        "updated_at": timestamp(),
    }
    temporary = ROOT / "repair_summary.json.tmp"
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(ROOT / "repair_summary.json")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args()
    CANDIDATES.mkdir(parents=True, exist_ok=True)
    trials = sorted(path for path in INPUTS.iterdir() if path.is_dir())
    key = load_key()
    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(run_trial, trial, key, args.retries): trial.name for trial in trials}
        for future in as_completed(futures):
            try:
                rows.append(future.result())
            except Exception as error:
                rows.append({"trial_id": futures[future], "status": "failed", "error": repr(error), "finished_at": timestamp()})
            write_summary(rows)
    write_summary(rows)
    return 1 if any(row.get("status") == "failed" for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
