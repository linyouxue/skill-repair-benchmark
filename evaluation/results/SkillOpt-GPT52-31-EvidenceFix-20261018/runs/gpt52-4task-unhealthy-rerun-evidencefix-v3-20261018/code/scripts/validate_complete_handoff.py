#!/usr/bin/env python3
"""Validate the structure and cross-links of the complete experiment handoff."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PATH_FIELDS = (
    "baseline_result", "baseline_job", "baseline_trajectory", "repair_loop",
    "before_skill", "after_skill", "best_skill", "diff", "method_result",
)
ROUND_PATH_FIELDS = (
    "diagnosis", "diagnosis_raw", "evidence_bundle", "optimization_manifest",
    "gate_result", "candidate_job", "candidate_skill_bundle", "trajectory", "verifier",
)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.package_root.resolve()
    issues: list[str] = []
    index = load(root / "metadata" / "TASK_ROUND_INDEX.json")
    summary = index.get("summary") or {}
    tasks = index.get("tasks") or []
    if len(tasks) != 46:
        issues.append(f"task count is {len(tasks)}, expected 46")
    rounds = sum(len(task.get("rounds") or []) for task in tasks)
    if rounds != 85:
        issues.append(f"round count is {rounds}, expected 85")

    for task in tasks:
        label = f"{task.get('track')}/{task.get('task_id')}"
        for field in PATH_FIELDS:
            value = task.get(field)
            if value and not (root / value).exists():
                issues.append(f"missing {label}.{field}: {value}")
        for round_row in task.get("rounds") or []:
            round_label = f"{label}/round_{round_row.get('round')}"
            for field in ROUND_PATH_FIELDS:
                value = round_row.get(field)
                if value and not (root / value).exists():
                    issues.append(f"missing {round_label}.{field}: {value}")
            for field in ("diagnosis_samples", "rewrite_records"):
                for value in round_row.get(field) or []:
                    if not (root / value).is_file():
                        issues.append(f"missing {round_label}.{field}: {value}")

    expected_submissions = {"gpt52-31": 31, "opus47-15": 15}
    for track, count in expected_submissions.items():
        submission = load(root / "submissions" / "outputs" / track / "submission.json")
        actual = len(submission.get("tasks") or [])
        if actual != count:
            issues.append(f"{track} submission has {actual} tasks, expected {count}")

    security = load(root / "metadata" / "SECURITY_SCAN.json")
    if security.get("passed") is not True:
        issues.append("SECURITY_SCAN.json does not pass")
    env_files = [
        path.relative_to(root).as_posix()
        for path in root.rglob(".env")
        if path.is_file()
    ]
    if env_files:
        issues.append(f"included .env files: {env_files}")

    payload = {
        "schema_version": "skillopt-complete-handoff-validation-v1",
        "passed": not issues,
        "task_count": len(tasks),
        "round_count": rounds,
        "candidate_skill_bundle_count": summary.get("candidate_skill_bundle_count"),
        "submission_task_counts": expected_submissions,
        "issues": issues,
    }
    (root / "metadata" / "VALIDATION.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not issues else 2


if __name__ == "__main__":
    raise SystemExit(main())
