#!/usr/bin/env python3
"""Export two evaluator-compatible submissions plus one combined index.

The evaluator schema has no run-health field.  Health and infrastructure
failures are therefore written to a sidecar ``run_status.json`` while the
evaluator-facing ``submission.json`` remains schema-compatible.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "experiments" / "submissions-dual-skillopt-20261008"


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def clean_location(path: str) -> str:
    value = path.replace("\\", "/").lstrip("./")
    for marker in ("/skills/", "before_skill/", "after_skill/", "best_skill/"):
        if marker in value:
            value = value.split(marker, 1)[1]
    return value or "SKILL.md"


def diagnoses_for(method_dir: Path) -> list[dict[str, Any]]:
    loop_path = method_dir / "workspace" / "repair_loop.json"
    if not loop_path.is_file():
        return []
    loop = read_object(loop_path)
    predictions: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in loop.get("rounds") or []:
        number = int(row.get("round") or 0)
        diagnosis_path = method_dir / "workspace" / f"round_{number}" / "diagnosis.json"
        if not diagnosis_path.is_file():
            continue
        diagnosis = read_object(diagnosis_path)
        for item in diagnosis.get("diagnosed_skills") or []:
            if not isinstance(item, dict):
                continue
            problem = str(item.get("diagnosis") or diagnosis.get("overall_diagnosis") or "").strip()
            repair = str(item.get("repair_instruction") or "").strip()
            description = problem
            if repair:
                description = f"{problem}\nRepair instruction: {repair}" if problem else repair
            if not description:
                continue
            file_path = clean_location(str(item.get("path") or "SKILL.md"))
            key = (file_path, problem, repair)
            if key in seen:
                continue
            seen.add(key)
            predictions.append(
                {
                    "prediction_id": f"P{len(predictions) + 1:03d}",
                    "description": description,
                    "locations": [
                        {
                            "file": file_path,
                            "section": f"SkillOpt round {number} diagnosis",
                        }
                    ],
                }
            )
    return predictions


def task_health(method_dir: Path, *, expected_rounds: int = 2) -> dict[str, Any]:
    """Apply the same fail-closed checks as ``validate_skillopt_task.py``."""
    issues: list[str] = []
    result_path = method_dir / "method_result.json"
    loop_path = method_dir / "workspace" / "repair_loop.json"
    result = read_object(result_path) if result_path.is_file() else {}
    loop = read_object(loop_path) if loop_path.is_file() else {}
    if not result_path.is_file():
        issues.append("method_result.json is missing")
    if not loop_path.is_file():
        issues.append("repair_loop.json is missing")
    rounds = loop.get("rounds") if isinstance(loop.get("rounds"), list) else []

    if result.get("comparable") is not True:
        issues.append("final method_result is not comparable")
    if result.get("prepare_only") is True:
        issues.append("task was prepared but not evaluated")
    if not (method_dir / "best_skill").is_dir():
        issues.append("best_skill bundle is missing")

    if result.get("task_passed") is True:
        if not 1 <= len(rounds) <= expected_rounds:
            issues.append(
                f"successful repair-loop round count is {len(rounds)}; "
                f"expected between 1 and {expected_rounds}"
            )
        elif not rounds or rounds[-1].get("passed") is not True:
            issues.append("successful result does not end with a passing gate round")
    elif len(rounds) != expected_rounds:
        issues.append(
            f"repair-loop round count is {len(rounds)}; expected {expected_rounds}"
        )

    round_statuses: list[dict[str, Any]] = []
    for number in range(1, len(rounds) + 1):
        round_dir = method_dir / "workspace" / f"round_{number}"
        diagnosis_path = round_dir / "diagnosis.json"
        gate_path = round_dir / "gate_result.json"
        diagnosis = read_object(diagnosis_path) if diagnosis_path.is_file() else {}
        gate = read_object(gate_path) if gate_path.is_file() else {}
        if not diagnosis_path.is_file():
            issues.append(f"round {number}: diagnosis.json is missing")
        if not gate_path.is_file():
            issues.append(f"round {number}: gate_result.json is missing")
        if diagnosis.get("fallback_used") is True:
            issues.append(f"round {number}: diagnosis used fallback")
        diagnosed = diagnosis.get("diagnosed_skills")
        if not isinstance(diagnosed, list) or not diagnosed:
            issues.append(f"round {number}: no diagnosed skills")
        if gate.get("comparable") is not True:
            issues.append(f"round {number}: gate result is not comparable")
        if gate.get("trajectory_complete") is not True:
            issues.append(f"round {number}: gate trajectory is incomplete")
        round_statuses.append(
            {
                "round": number,
                "rollout_id": gate.get("rollout_id"),
                "comparable": gate.get("comparable") is True,
                "task_passed": gate.get("task_passed"),
                "reward": gate.get("reward"),
                "execution_ok": gate.get("execution_ok"),
                "trajectory_complete": gate.get("trajectory_complete"),
                "termination_reason": gate.get("termination_reason"),
                "error": gate.get("error"),
                "error_category": gate.get("error_category"),
                "verifier_error": gate.get("verifier_error"),
                "verifier_error_category": gate.get("verifier_error_category"),
                "export_error": gate.get("export_error"),
            }
        )

    return {
        "healthy": not issues,
        "comparable": result.get("comparable") is True,
        "task_passed": result.get("task_passed"),
        "reward": result.get("reward"),
        "rollout_id": result.get("rollout_id"),
        "rounds_checked": len(rounds),
        "rounds": round_statuses,
        "issues": issues,
    }


def export_track(
    *,
    run_id: str,
    template: Path,
    output_dir: Path,
    include_unhealthy: bool = False,
) -> dict[str, Any]:
    source = read_object(template)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tasks_dir = output_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    exported_tasks: list[dict[str, Any]] = []
    task_statuses: list[dict[str, Any]] = []

    for template_task in source.get("tasks") or []:
        task_id = str(template_task["task_id"])
        method_dir = ROOT / "experiments" / run_id / "methods" / "skillopt" / task_id
        health = task_health(method_dir)
        if not health["healthy"] and not include_unhealthy:
            raise RuntimeError(f"Cannot export unhealthy result: {run_id}/{task_id}")

        source_bundle = method_dir / "best_skill"
        bundle_source = "skillopt_best_skill"
        if not source_bundle.is_dir():
            source_bundle = template.parent / "originals" / task_id / "skills"
            bundle_source = "original_skill_fallback"
        if not source_bundle.is_dir():
            raise FileNotFoundError(source_bundle)
        destination = tasks_dir / task_id / "skills"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_bundle, destination, symlinks=False)
        submission_task = {
            "task_id": task_id,
            "diagnoses": diagnoses_for(method_dir),
            "repaired_bundle": f"tasks/{task_id}/skills",
        }
        if health["rollout_id"]:
            submission_task["executor_run_id"] = health["rollout_id"]
        exported_tasks.append(submission_task)
        task_statuses.append(
            {
                "task_id": task_id,
                **health,
                "bundle_source": bundle_source,
                "diagnosis_count": len(submission_task["diagnoses"]),
            }
        )

    payload = {
        "method_id": "skillopt",
        "benchmark_version": source["benchmark_version"],
        "tasks": exported_tasks,
    }
    submission_path = output_dir / "submission.json"
    submission_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    healthy_count = sum(1 for row in task_statuses if row["healthy"])
    status_payload = {
        "schema_version": "skillopt-run-status-v1",
        "run_id": run_id,
        "method_id": "skillopt",
        "benchmark_version": payload["benchmark_version"],
        "task_count": len(task_statuses),
        "healthy_count": healthy_count,
        "unhealthy_count": len(task_statuses) - healthy_count,
        "tasks": task_statuses,
        "note": (
            "This sidecar is not evaluator input. submission.json remains evaluator-compatible; "
            "unhealthy tasks are retained here with fail-closed validation issues."
        ),
    }
    status_path = output_dir / "run_status.json"
    status_path.write_text(
        json.dumps(status_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "status": "complete" if healthy_count == len(task_statuses) else "complete_with_unhealthy",
        "run_id": run_id,
        "benchmark_version": payload["benchmark_version"],
        "task_count": len(exported_tasks),
        "healthy_count": healthy_count,
        "unhealthy_count": len(task_statuses) - healthy_count,
        "unhealthy_tasks": [row["task_id"] for row in task_statuses if not row["healthy"]],
        "submission": str(submission_path.relative_to(DEFAULT_OUT)),
        "run_status": str(status_path.relative_to(DEFAULT_OUT)),
    }


def export_track_when_complete(
    *,
    run_id: str,
    template: Path,
    output_dir: Path,
    include_unhealthy: bool = False,
) -> dict[str, Any]:
    """Export one track without making the other track's progress a dependency."""
    source = read_object(template)
    missing: list[str] = []
    for template_task in source.get("tasks") or []:
        task_id = str(template_task["task_id"])
        method_dir = ROOT / "experiments" / run_id / "methods" / "skillopt" / task_id
        result_path = method_dir / "method_result.json"
        loop_path = method_dir / "workspace" / "repair_loop.json"
        if not result_path.is_file() or not loop_path.is_file() or not (method_dir / "best_skill").is_dir():
            missing.append(task_id)
            continue
        if read_object(result_path).get("comparable") is not True:
            missing.append(task_id)
    if missing and not include_unhealthy:
        # Never leave a partial directory that could be mistaken for a valid
        # evaluator submission from an earlier interrupted export.
        if output_dir.exists():
            shutil.rmtree(output_dir)
        return {
            "status": "pending",
            "run_id": run_id,
            "benchmark_version": source["benchmark_version"],
            "task_count": len(source.get("tasks") or []),
            "missing_or_invalid_count": len(missing),
            "missing_or_invalid_tasks": missing,
            "submission": None,
        }
    return export_track(
        run_id=run_id,
        template=template,
        output_dir=output_dir,
        include_unhealthy=include_unhealthy,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--gpt-run-id", default="gpt52-31-skillopt-gpt52-ai360-20261011")
    parser.add_argument("--opus-run-id", default="opus47-15-skillopt-opus47-tatu-20261008")
    parser.add_argument(
        "--include-unhealthy",
        action="store_true",
        help="Export every configured task and record fail-closed health in run_status.json.",
    )
    args = parser.parse_args()
    out = args.output_root.resolve()

    tracks = {
        "gpt52_baseline_31": export_track_when_complete(
            run_id=args.gpt_run_id,
            template=out / "gold" / "gpt52-31" / "submission.template.json",
            output_dir=out / "outputs" / "gpt52-31",
            include_unhealthy=args.include_unhealthy,
        ),
        "opus47_baseline_15": export_track_when_complete(
            run_id=args.opus_run_id,
            template=out / "gold" / "opus47-15" / "submission.template.json",
            output_dir=out / "outputs" / "opus47-15",
            include_unhealthy=args.include_unhealthy,
        ),
    }
    combined = {
        "schema_version": "skillopt-dual-experiment-index-v1",
        "method_id": "skillopt",
        "created_at": datetime.now(UTC).isoformat(),
        "tracks": tracks,
        "note": (
            "Each track submission is evaluator-compatible; benchmark versions differ, so this file "
            "is an index rather than a merged evaluator payload. Per-task health is in run_status.json."
        ),
    }
    (out / "submission.json").write_text(
        json.dumps(combined, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(combined, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
