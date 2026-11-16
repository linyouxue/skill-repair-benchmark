#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=f"smoke-{datetime.now(UTC):%Y%m%dT%H%M%SZ}")
    parser.add_argument("--task", action="append", default=["dialogue-parser"])
    parser.add_argument("--skip-paid", action="store_true")
    args = parser.parse_args()

    check_cmd = [sys.executable, "scripts/check_environment.py"]
    if args.skip_paid:
        check_cmd.append("--allow-missing-api-key")
    run(check_cmd)
    if args.skip_paid:
        print(f"skip paid rollouts; run_id={args.run_id}")
        return 0

    for task_id in args.task:
        run([sys.executable, "scripts/run_original_baseline.py", "--run-id", args.run_id, "--task", task_id])
    print("Method adapters are wired. Use scripts/run_method.py for paid method-skill evaluation.")
    print(f"run_id={args.run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
