#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNS = (
    "gpt52-31-skillopt-gpt52-ai360-20261011",
    "opus47-15-skillopt-opus47-tatu-20261008",
)


for run_id in RUNS:
    run_dir = ROOT / "experiments" / run_id
    tasks = [line.strip() for line in (run_dir / "tasks.txt").read_text().splitlines() if line.strip()]
    completed = passed = comparable = errors = 0
    active: list[str] = []
    missing: list[str] = []
    for task in tasks:
        method_dir = run_dir / "methods" / "skillopt" / task
        result_path = method_dir / "method_result.json"
        loop_path = method_dir / "workspace" / "repair_loop.json"
        if result_path.is_file() and loop_path.is_file():
            completed += 1
            try:
                result = json.loads(result_path.read_text())
            except json.JSONDecodeError:
                errors += 1
                continue
            passed += result.get("task_passed") is True
            comparable += result.get("comparable") is True
            errors += bool(result.get("error"))
        elif method_dir.exists():
            active.append(task)
        else:
            missing.append(task)
    print(
        json.dumps(
            {
                "run_id": run_id,
                "total": len(tasks),
                "completed": completed,
                "passed": passed,
                "comparable": comparable,
                "errors": errors,
                "active": active,
                "queued": len(missing),
            },
            ensure_ascii=False,
        )
    )
