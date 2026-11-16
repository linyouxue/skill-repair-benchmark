#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.common.paths import load_task_ids  # noqa: E402


def load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def passed(result: dict) -> str:
    value = result.get("task_passed")
    return "" if value is None else str(bool(value)).lower()


def comparable(result: dict) -> str:
    value = result.get("comparable")
    return "" if value is None else str(bool(value)).lower()


def category(result: dict, missing: str = "missing_result") -> str:
    if not result:
        return missing
    return result.get("error_category") or result.get("verifier_error_category") or ""


def score(result: dict) -> str:
    for key in ("reward", "score", "metric"):
        if key in result:
            return str(result[key])
    return ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    run_root = ROOT / "experiments" / args.run_id
    summary_dir = run_root / "summaries"
    summary_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    non_comparable = []
    for task_id in load_task_ids():
        baseline = load_json(run_root / "baseline" / "original-skill" / task_id / "benchmark_result.json")
        skillopt = load_json(run_root / "methods" / "skillopt" / task_id / "method_result.json")
        lite = load_json(run_root / "methods" / "skillopt-lite" / task_id / "method_result.json")
        row = {
            "task_id": task_id,
            "baseline_passed": passed(baseline),
            "baseline_comparable": comparable(baseline),
            "baseline_failure_category": category(baseline),
            "skillopt_passed": passed(skillopt),
            "skillopt_lite_passed": passed(lite),
            "skillopt_comparable": comparable(skillopt),
            "skillopt_lite_comparable": comparable(lite),
            "skillopt_failure_category": category(skillopt),
            "skillopt_lite_failure_category": category(lite),
            "baseline_score_or_reward": score(baseline),
            "skillopt_score_or_reward": score(skillopt),
            "skillopt_lite_score_or_reward": score(lite),
            "skillopt_duration": str(skillopt.get("duration_sec", "")),
            "skillopt_lite_duration": str(lite.get("duration_sec", "")),
            "skillopt_token_or_cost": str(skillopt.get("usage", "")),
            "skillopt_lite_token_or_cost": str(lite.get("usage", "")),
            "notes": "",
        }
        rows.append(row)
        for method, result, cat_key in (
            ("skillopt", skillopt, "skillopt_failure_category"),
            ("skillopt-lite", lite, "skillopt_lite_failure_category"),
        ):
            if not result or result.get("comparable") is not True:
                non_comparable.append({"task_id": task_id, "method": method, "category": row[cat_key]})

    fieldnames = list(rows[0].keys()) if rows else []
    with (summary_dir / "summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    with (summary_dir / "non_comparable.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["task_id", "method", "category"])
        writer.writeheader()
        writer.writerows(non_comparable)

    skillopt_pass = sum(1 for row in rows if row["skillopt_passed"] == "true" and row["skillopt_comparable"] == "true")
    lite_pass = sum(1 for row in rows if row["skillopt_lite_passed"] == "true" and row["skillopt_lite_comparable"] == "true")
    baseline_pass = sum(1 for row in rows if row["baseline_passed"] == "true" and row["baseline_comparable"] == "true")
    lines = [
        f"# Summary {args.run_id}",
        "",
        f"- Tasks: {len(rows)}",
        f"- Baseline comparable pass: {baseline_pass}",
        f"- SkillOpt comparable pass: {skillopt_pass}",
        f"- SkillOpt-Lite comparable pass: {lite_pass}",
        f"- Non-comparable or missing method results: {len(non_comparable)}",
        "",
    ]
    (summary_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(summary_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
