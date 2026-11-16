#!/usr/bin/env python3
"""Fail closed when a completed SkillOpt task lacks usable repair evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load_object(path: Path, issues: list[str]) -> dict[str, Any]:
    if not path.is_file():
        issues.append(f"missing: {path}")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        issues.append(f"invalid JSON: {path}: {exc}")
        return {}
    if not isinstance(value, dict):
        issues.append(f"expected JSON object: {path}")
        return {}
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--method", default="skillopt")
    parser.add_argument("--expected-rounds", type=int, default=2)
    args = parser.parse_args()

    method_dir = ROOT / "experiments" / args.run_id / "methods" / args.method / args.task
    issues: list[str] = []
    result = load_object(method_dir / "method_result.json", issues)
    loop = load_object(method_dir / "workspace" / "repair_loop.json", issues)
    rounds = loop.get("rounds") if isinstance(loop.get("rounds"), list) else []

    if result.get("comparable") is not True:
        issues.append("final method_result is not comparable")
    if result.get("prepare_only") is True:
        issues.append("task was prepared but not evaluated")
    if not (method_dir / "best_skill").is_dir():
        issues.append("best_skill bundle is missing")

    if result.get("task_passed") is True:
        if not 1 <= len(rounds) <= args.expected_rounds:
            issues.append(
                f"successful repair-loop round count is {len(rounds)}; "
                f"expected between 1 and {args.expected_rounds}"
            )
        elif not rounds or rounds[-1].get("passed") is not True:
            issues.append("successful result does not end with a passing gate round")
    elif len(rounds) != args.expected_rounds:
        issues.append(
            f"repair-loop round count is {len(rounds)}; expected {args.expected_rounds}"
        )

    for number in range(1, len(rounds) + 1):
        round_dir = method_dir / "workspace" / f"round_{number}"
        diagnosis = load_object(round_dir / "diagnosis.json", issues)
        gate = load_object(round_dir / "gate_result.json", issues)
        if diagnosis.get("fallback_used") is True:
            issues.append(f"round {number}: diagnosis used fallback")
        diagnosed = diagnosis.get("diagnosed_skills")
        if not isinstance(diagnosed, list) or not diagnosed:
            issues.append(f"round {number}: no diagnosed skills")
        if gate.get("comparable") is not True:
            issues.append(f"round {number}: gate result is not comparable")
        if gate.get("trajectory_complete") is not True:
            issues.append(f"round {number}: gate trajectory is incomplete")

    payload = {
        "run_id": args.run_id,
        "task_id": args.task,
        "method": args.method,
        "healthy": not issues,
        "task_passed": result.get("task_passed"),
        "rounds_checked": len(rounds),
        "issues": issues,
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
