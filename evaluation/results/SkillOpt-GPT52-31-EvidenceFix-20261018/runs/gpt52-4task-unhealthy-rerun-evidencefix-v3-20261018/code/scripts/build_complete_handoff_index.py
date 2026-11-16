#!/usr/bin/env python3
"""Build an auditable task/round/candidate index for the SkillOpt handoff."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


RUNS = (
    ("gpt52-31", "gpt52-31-skillopt-gpt52-ai360-20261011"),
    ("opus47-15", "opus47-15-skillopt-opus47-tatu-20261008"),
)


def read_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def relative(root: Path, path: Path) -> str | None:
    return path.relative_to(root).as_posix() if path.exists() else None


def list_files(root: Path, directory: Path, pattern: str = "*") -> list[str]:
    if not directory.is_dir():
        return []
    return [path.relative_to(root).as_posix() for path in sorted(directory.glob(pattern)) if path.is_file()]


def find_baseline_job(run_dir: Path, rollout_id: str | None) -> Path | None:
    if not rollout_id:
        return None
    candidate = run_dir / "jobs" / "baseline-original-skill" / rollout_id
    return candidate if candidate.is_dir() else None


def build_index(package_root: Path) -> dict[str, Any]:
    status_by_track: dict[str, dict[str, dict[str, Any]]] = {}
    for track, _ in RUNS:
        status = read_object(package_root / "submissions" / "outputs" / track / "run_status.json")
        status_by_track[track] = {
            str(row.get("task_id")): row
            for row in status.get("tasks") or []
            if isinstance(row, dict) and row.get("task_id")
        }

    tasks: list[dict[str, Any]] = []
    flat_rounds: list[dict[str, Any]] = []
    for track, run_id in RUNS:
        run_dir = package_root / "runs" / run_id
        metadata = read_object(run_dir / "metadata.json")
        task_ids = [
            str(row["task_id"])
            for row in metadata.get("tasks") or []
            if isinstance(row, dict) and row.get("task_id")
        ]
        for task_id in task_ids:
            baseline_dir = run_dir / "baseline" / "original-skill" / task_id
            baseline_pointer = read_object(baseline_dir / "rollout_pointer.json")
            baseline_result = read_object(baseline_dir / "benchmark_result.json")
            baseline_rollout_id = baseline_pointer.get("rollout_id") or baseline_result.get("rollout_id")
            baseline_job = find_baseline_job(run_dir, str(baseline_rollout_id) if baseline_rollout_id else None)

            method_dir = run_dir / "methods" / "skillopt" / task_id
            method_result = read_object(method_dir / "method_result.json")
            loop = read_object(method_dir / "workspace" / "repair_loop.json")
            rejected = loop.get("rejected_buffer") if isinstance(loop.get("rejected_buffer"), list) else []
            rounds: list[dict[str, Any]] = []
            for row in loop.get("rounds") or []:
                if not isinstance(row, dict):
                    continue
                number = int(row.get("round") or 0)
                round_dir = method_dir / "workspace" / f"round_{number}"
                gate = read_object(round_dir / "gate_result.json")
                diagnosis = read_object(round_dir / "diagnosis.json")
                manifest = read_object(round_dir / "optimization_manifest.json")
                rollout_id = gate.get("rollout_id")
                rollout_dir = run_dir / "jobs" / "skillopt" / str(rollout_id) if rollout_id else None
                rejected_rows = [
                    item
                    for item in rejected
                    if isinstance(item, dict) and int(item.get("round") or 0) == number
                ]
                round_record = {
                    "round": number,
                    "decision": row.get("decision"),
                    "decision_reason": row.get("reason") or (
                        rejected_rows[0].get("reason") if rejected_rows else None
                    ),
                    "score": row.get("score"),
                    "passed": row.get("passed"),
                    "best_score_after_round": row.get("best_score"),
                    "best_passed_after_round": row.get("best_passed"),
                    "failure_evidence_size": row.get("failure_evidence_size"),
                    "rejected_buffer_size": row.get("rejected_buffer_size"),
                    "diagnosed_skill_count": len(diagnosis.get("diagnosed_skills") or []),
                    "rewritten_skill_count": len(manifest.get("rewritten_files") or []),
                    "diagnosis_samples": list_files(
                        package_root, round_dir / "diagnosis_samples", "sample_*.json"
                    ),
                    "diagnosis": relative(package_root, round_dir / "diagnosis.json"),
                    "diagnosis_raw": relative(package_root, round_dir / "diagnosis_raw.json"),
                    "evidence_bundle": relative(package_root, round_dir / "evidence_bundle.json"),
                    "optimization_manifest": relative(
                        package_root, round_dir / "optimization_manifest.json"
                    ),
                    "rewrite_records": list_files(package_root, round_dir / "rewrite_raw", "*.json"),
                    "gate_result": relative(package_root, round_dir / "gate_result.json"),
                    "rollout_id": rollout_id,
                    "candidate_job": relative(package_root, rollout_dir) if rollout_dir else None,
                    "candidate_skill_bundle": (
                        relative(package_root, rollout_dir / "inputs" / "skills")
                        if rollout_dir else None
                    ),
                    "trajectory": (
                        relative(package_root, rollout_dir / "trajectory") if rollout_dir else None
                    ),
                    "verifier": relative(package_root, rollout_dir / "verifier") if rollout_dir else None,
                    "gate_comparable": gate.get("comparable"),
                    "gate_task_passed": gate.get("task_passed"),
                    "gate_reward": gate.get("reward"),
                    "gate_execution_ok": gate.get("execution_ok"),
                    "gate_error": gate.get("error"),
                    "gate_error_category": gate.get("error_category"),
                    "verifier_error": gate.get("verifier_error"),
                    "verifier_error_category": gate.get("verifier_error_category"),
                    "rejected_proposals": rejected_rows,
                }
                rounds.append(round_record)
                flat_rounds.append(
                    {
                        "track": track,
                        "run_id": run_id,
                        "task_id": task_id,
                        **round_record,
                    }
                )

            task_status = status_by_track.get(track, {}).get(task_id, {})
            tasks.append(
                {
                    "track": track,
                    "run_id": run_id,
                    "task_id": task_id,
                    "healthy": task_status.get("healthy"),
                    "health_issues": task_status.get("issues") or [],
                    "baseline_rollout_id": baseline_rollout_id,
                    "baseline_result": relative(package_root, baseline_dir / "benchmark_result.json"),
                    "baseline_job": relative(package_root, baseline_job) if baseline_job else None,
                    "baseline_trajectory": (
                        relative(package_root, baseline_job / "trajectory") if baseline_job else None
                    ),
                    "repair_loop": relative(package_root, method_dir / "workspace" / "repair_loop.json"),
                    "before_skill": relative(package_root, method_dir / "before_skill"),
                    "after_skill": relative(package_root, method_dir / "after_skill"),
                    "best_skill": relative(package_root, method_dir / "best_skill"),
                    "diff": relative(package_root, method_dir / "diff.patch"),
                    "method_result": relative(package_root, method_dir / "method_result.json"),
                    "selected_rollout_id": method_result.get("rollout_id"),
                    "selected_comparable": method_result.get("comparable"),
                    "selected_task_passed": method_result.get("task_passed"),
                    "selected_reward": method_result.get("reward"),
                    "round_count": len(rounds),
                    "rounds": rounds,
                    "terminal_logs": list_files(package_root, run_dir / "logs", "*.log"),
                }
            )

    decisions: dict[str, int] = {}
    for row in flat_rounds:
        decision = str(row.get("decision") or "missing")
        decisions[decision] = decisions.get(decision, 0) + 1
    summary = {
        "track_count": len(RUNS),
        "task_count": len(tasks),
        "healthy_task_count": sum(row.get("healthy") is True for row in tasks),
        "unhealthy_task_count": sum(row.get("healthy") is False for row in tasks),
        "round_count": len(flat_rounds),
        "candidate_rollout_count": sum(bool(row.get("rollout_id")) for row in flat_rounds),
        "candidate_skill_bundle_count": sum(bool(row.get("candidate_skill_bundle")) for row in flat_rounds),
        "diagnosis_sample_count": sum(len(row.get("diagnosis_samples") or []) for row in flat_rounds),
        "rounds_with_individual_diagnosis_samples": sum(
            bool(row.get("diagnosis_samples")) for row in flat_rounds
        ),
        "rounds_without_individual_diagnosis_samples": sum(
            not bool(row.get("diagnosis_samples")) for row in flat_rounds
        ),
        "rewrite_record_count": sum(len(row.get("rewrite_records") or []) for row in flat_rounds),
        "gate_non_comparable_count": sum(row.get("gate_comparable") is False for row in flat_rounds),
        "decisions": decisions,
    }
    return {
        "schema_version": "skillopt-complete-handoff-index-v1",
        "summary": summary,
        "tasks": tasks,
    }


def write_csv(path: Path, index: dict[str, Any]) -> None:
    fields = [
        "track", "run_id", "task_id", "healthy", "round", "decision",
        "decision_reason", "gate_comparable", "gate_task_passed", "gate_reward",
        "gate_execution_ok", "rollout_id", "diagnosed_skill_count",
        "rewritten_skill_count", "failure_evidence_size", "rejected_buffer_size",
        "candidate_skill_bundle", "gate_result", "verifier_error_category",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for task in index["tasks"]:
            if not task["rounds"]:
                writer.writerow({"track": task["track"], "run_id": task["run_id"], "task_id": task["task_id"], "healthy": task["healthy"]})
                continue
            for round_row in task["rounds"]:
                writer.writerow(
                    {
                        key: (
                            task.get(key)
                            if key in {"track", "run_id", "task_id", "healthy"}
                            else round_row.get(key)
                        )
                        for key in fields
                    }
                )


def write_manifest(package_root: Path, output: Path) -> None:
    rows: list[str] = []
    for path in sorted(package_root.rglob("*")):
        if not path.is_file() or path == output:
            continue
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        rows.append(f"{digest.hexdigest()}  {path.relative_to(package_root).as_posix()}")
    output.write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--write-manifest", action="store_true")
    args = parser.parse_args()
    root = args.package_root.resolve()
    metadata = root / "metadata"
    metadata.mkdir(parents=True, exist_ok=True)
    index = build_index(root)
    (metadata / "TASK_ROUND_INDEX.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_csv(metadata / "TASK_ROUND_INDEX.csv", index)
    (metadata / "ARTIFACT_COVERAGE.json").write_text(
        json.dumps(index["summary"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if args.write_manifest:
        write_manifest(root, metadata / "FILE_MANIFEST.sha256")
    print(json.dumps(index["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
