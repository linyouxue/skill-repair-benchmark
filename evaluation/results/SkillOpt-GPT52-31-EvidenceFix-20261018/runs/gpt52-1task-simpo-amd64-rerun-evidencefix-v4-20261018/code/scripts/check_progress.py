#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.common.paths import load_task_ids  # noqa: E402


def load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"error_category": "invalid_json", "error": repr(exc)}


def state(result: dict, path: Path) -> str:
    if not path.exists():
        return "missing"
    if result.get("error_category"):
        return f"failed:{result['error_category']}"
    if result.get("comparable") is True and result.get("task_passed") is True:
        return "passed"
    if result.get("comparable") is True and result.get("task_passed") is False:
        return "task_failed"
    if result.get("comparable") is False:
        return "non_comparable"
    return "present"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--tail", type=int, default=0, help="Show last N lines from latest log file.")
    args = parser.parse_args()

    run_root = ROOT / "experiments" / args.run_id
    tasks = load_task_ids()
    buckets = {
        "baseline": [],
        "skillopt": [],
        "skillopt-lite": [],
    }
    for task_id in tasks:
        paths = {
            "baseline": run_root / "baseline" / "original-skill" / task_id / "benchmark_result.json",
            "skillopt": run_root / "methods" / "skillopt" / task_id / "method_result.json",
            "skillopt-lite": run_root / "methods" / "skillopt-lite" / task_id / "method_result.json",
        }
        for name, path in paths.items():
            buckets[name].append((task_id, state(load_json(path), path)))

    for name, entries in buckets.items():
        done = sum(1 for _, s in entries if s != "missing")
        passed = sum(1 for _, s in entries if s == "passed")
        failed = [f"{task}:{s}" for task, s in entries if s not in {"missing", "passed", "task_failed"}]
        task_failed = sum(1 for _, s in entries if s == "task_failed")
        print(f"{name}: {done}/{len(entries)} present, passed={passed}, task_failed={task_failed}, issues={len(failed)}")
        if failed:
            for item in failed[:12]:
                print(f"  - {item}")
            if len(failed) > 12:
                print(f"  - ... {len(failed) - 12} more")

    if args.tail:
        log_dir = run_root / "logs"
        logs = sorted([p for p in log_dir.glob("*.log") if p.is_file()], key=lambda p: p.stat().st_mtime)
        if logs:
            latest = logs[-1]
            print(f"\nlatest log: {latest}")
            lines = latest.read_text(encoding="utf-8", errors="replace").splitlines()
            for line in lines[-args.tail :]:
                print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
