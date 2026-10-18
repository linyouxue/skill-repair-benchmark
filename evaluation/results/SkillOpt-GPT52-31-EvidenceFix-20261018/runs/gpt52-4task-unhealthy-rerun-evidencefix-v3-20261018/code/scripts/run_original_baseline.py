#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.common.executor_api import run_original, write_json  # noqa: E402
from adapters.common.paths import load_task_ids  # noqa: E402


def baseline_failure(task_id: str, run_id: str, exc: BaseException) -> None:
    out_dir = ROOT / "experiments" / run_id / "baseline" / "original-skill" / task_id
    write_json(
        out_dir / "benchmark_result.json",
        {
            "task_id": task_id,
            "task_passed": False,
            "comparable": False,
            "error_category": "baseline_execution_failed",
            "error": repr(exc),
            "traceback": traceback.format_exc(),
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=f"run-{datetime.now(UTC):%Y%m%dT%H%M%SZ}")
    parser.add_argument("--task", action="append", help="Task id. Can be passed multiple times.")
    args = parser.parse_args()

    task_ids = args.task or load_task_ids()
    failed = False
    for task_id in task_ids:
        print(f"[baseline] {task_id}")
        try:
            result = run_original(task_id, args.run_id)
            print(f"  comparable={result.get('comparable')} passed={result.get('task_passed')}")
        except Exception as exc:  # noqa: BLE001
            failed = True
            baseline_failure(task_id, args.run_id, exc)
            print(f"  failed={exc!r}", file=sys.stderr)
    print(f"run_id={args.run_id}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
