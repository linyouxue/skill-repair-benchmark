#!/usr/bin/env python3
"""Export one evaluator submission from task results selected across runs.

The raw run directories remain immutable.  This exporter copies only the
selected best Skill bundles and compact result records, and writes provenance
links back to every raw diagnosis, candidate, gate attempt, trajectory, verifier
record, and terminal log.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from export_dual_submissions import diagnoses_for, read_object, task_health


ROOT = Path(__file__).resolve().parents[1]


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def task_ids(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def bundle_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        name = path.relative_to(root).as_posix().encode("utf-8")
        body = path.read_bytes()
        digest.update(len(name).to_bytes(8, "big"))
        digest.update(name)
        digest.update(len(body).to_bytes(8, "big"))
        digest.update(body)
    return f"sha256:{digest.hexdigest()}"


def repair_rows(result: dict[str, Any]) -> tuple[list[str], int, list[dict[str, Any]]]:
    decisions: list[str] = []
    invalid_count = 0
    rollouts: list[dict[str, Any]] = []
    for round_row in result.get("repair_loop") or []:
        number = int(round_row.get("round") or 0)
        decisions.append(str(round_row.get("decision") or ""))
        for attempt in round_row.get("gate_attempts") or []:
            valid = attempt.get("valid") is True
            if not valid:
                invalid_count += 1
            rollout_dir = Path(str(attempt.get("rollout_dir") or ""))
            rollouts.append(
                {
                    "round": number,
                    "attempt": attempt.get("attempt"),
                    "valid": valid,
                    "invalid_reason": attempt.get("invalid_reason"),
                    "rollout_id": attempt.get("rollout_id"),
                    "rollout_dir": relative(rollout_dir) if str(rollout_dir) else None,
                    "attempt_record": relative(Path(str(attempt.get("result"))))
                    if attempt.get("result")
                    else None,
                }
            )
    return decisions, invalid_count, rollouts


def terminal_logs_for(run_root: Path, task_id: str) -> list[str]:
    logs: list[str] = []
    candidates = [
        *(run_root / "logs").glob("*.log"),
        *(run_root / "terminal_logs").glob("*.log"),
    ]
    for path in sorted(candidates):
        if not path.is_file():
            continue
        body = path.read_text(encoding="utf-8", errors="replace")
        if task_id in body:
            logs.append(relative(path))
    return logs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    manifest = read_object(manifest_path)
    output = args.output.resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    task_file = ROOT / str(manifest["task_list"])
    ordered_tasks = task_ids(task_file)
    overrides = {
        str(task): str(run_id)
        for task, run_id in (manifest.get("task_run_overrides") or {}).items()
    }
    final_result_overrides = {
        str(task): str(run_id)
        for task, run_id in (
            manifest.get("final_result_run_overrides") or {}
        ).items()
    }
    default_run = str(manifest["default_run_id"])

    submission_tasks: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    for task_id in ordered_tasks:
        run_id = overrides.get(task_id, default_run)
        result_run_id = final_result_overrides.get(task_id, run_id)
        run_root = ROOT / "experiments" / run_id
        result_run_root = ROOT / "experiments" / result_run_id
        method_dir = run_root / "methods" / "skillopt" / task_id
        result_method_dir = result_run_root / "methods" / "skillopt" / task_id
        result_path = result_method_dir / "method_result.json"
        result = read_object(result_path)
        health = task_health(method_dir)
        issues = list(health["issues"])
        if result_run_id != run_id:
            if result.get("comparable") is not True:
                issues.append("final frozen result is not comparable")
            if result.get("execution_ok") is not True:
                issues.append("final frozen execution is not healthy")
            if result.get("trajectory_complete") is not True:
                issues.append("final frozen trajectory is incomplete")
            health = {
                **health,
                "healthy": not issues,
                "comparable": result.get("comparable") is True,
                "task_passed": result.get("task_passed"),
                "reward": result.get("reward"),
                "rollout_id": result.get("rollout_id"),
                "issues": issues,
            }
        if not health["healthy"]:
            raise RuntimeError(
                f"selected result failed closed health audit: {run_id}/{task_id}: "
                + "; ".join(health["issues"])
            )

        best_skill = method_dir / "best_skill"
        destination = output / "tasks" / task_id / "skills"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(best_skill, destination, symlinks=False)

        compact_dir = output / "selected_results" / task_id
        compact_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(result_path, compact_dir / "method_result.json")
        repair_loop_path = method_dir / "workspace" / "repair_loop.json"
        shutil.copy2(repair_loop_path, compact_dir / "repair_loop.json")

        diagnoses = diagnoses_for(method_dir)
        submission_tasks.append(
            {
                "task_id": task_id,
                "diagnoses": diagnoses,
                "repaired_bundle": f"tasks/{task_id}/skills",
                "executor_run_id": result.get("rollout_id"),
            }
        )

        repair_result = read_object(method_dir / "method_result.json")
        decisions, invalid_attempts, rollout_records = repair_rows(repair_result)
        terminal_logs = terminal_logs_for(run_root, task_id)
        if result_run_id != run_id:
            terminal_logs = sorted(
                set(terminal_logs + terminal_logs_for(result_run_root, task_id))
            )
        status = {
            "task_id": task_id,
            "source_run_id": run_id,
            "final_result_run_id": result_run_id,
            **health,
            "selected_result_model": result.get("model"),
            "selected_provider_route": result.get("provider_route"),
            "selected_stage": result.get("stage"),
            "selected_original_baseline_after_revert": result.get("stage")
            == "original-skill",
            "invalid_gate_attempt_count": invalid_attempts,
            "decisions": decisions,
            "diagnosis_count": len(diagnoses),
            "bundle_sha256": bundle_sha256(best_skill),
        }
        statuses.append(status)
        evidence.append(
            {
                "task_id": task_id,
                "source_run_id": run_id,
                "final_result_run_id": result_run_id,
                "method_result": relative(result_path),
                "repair_loop": relative(repair_loop_path),
                "method_workspace": relative(method_dir / "workspace"),
                "before_skill": relative(method_dir / "before_skill"),
                "best_skill": relative(best_skill),
                "final_rollout": relative(Path(str(result.get("rollout_dir"))))
                if result.get("rollout_dir")
                else None,
                "source_task": relative(run_root / "source_tasks" / task_id)
                if (run_root / "source_tasks" / task_id).exists()
                else None,
                "baseline": relative(
                    run_root / "baseline" / "original-skill" / task_id
                )
                if (run_root / "baseline" / "original-skill" / task_id).exists()
                else None,
                "run_metadata": relative(run_root / "metadata.json")
                if (run_root / "metadata.json").exists()
                else None,
                "run_commands": relative(run_root / "commands")
                if (run_root / "commands").exists()
                else None,
                "code_snapshot": relative(run_root / "code")
                if (run_root / "code").exists()
                else None,
                "task_patch_notes": relative(run_root / "TASK_PATCHES.md")
                if (run_root / "TASK_PATCHES.md").is_file()
                else None,
                "invalid_attempt_diagnosis": relative(run_root / "HANG_DIAGNOSIS.md")
                if (run_root / "HANG_DIAGNOSIS.md").is_file()
                else None,
                "rollouts": rollout_records,
                "terminal_logs": terminal_logs,
            }
        )
        summary_rows.append(
            {
                "task_id": task_id,
                "task_passed": str(result.get("task_passed") is True).lower(),
                "comparable": str(result.get("comparable") is True).lower(),
                "reward": result.get("reward"),
                "source_run_id": run_id,
                "final_result_run_id": result_run_id,
                "rollout_id": result.get("rollout_id"),
                "rounds": len(repair_result.get("repair_loop") or []),
                "decisions": ",".join(decisions),
                "invalid_gate_attempts": invalid_attempts,
                "diagnoses": len(diagnoses),
            }
        )

    submission = {
        "method_id": str(manifest.get("method_id") or "skillopt"),
        "benchmark_version": str(manifest["benchmark_version"]),
        "tasks": submission_tasks,
    }
    write_json(output / "submission.json", submission)
    write_json(
        output / "run_status.json",
        {
            "schema_version": "skillopt-composite-run-status-v1",
            "composite_id": manifest.get("composite_id"),
            "task_count": len(statuses),
            "healthy_count": sum(row["healthy"] is True for row in statuses),
            "comparable_count": sum(row["comparable"] is True for row in statuses),
            "passed_count": sum(row["task_passed"] is True for row in statuses),
            "failed_count": sum(row["task_passed"] is False for row in statuses),
            "invalid_gate_attempts_preserved": sum(
                int(row["invalid_gate_attempt_count"]) for row in statuses
            ),
            "superseded_invalid_runs_preserved": list(
                manifest.get("superseded_invalid_runs") or []
            ),
            "independent_validation_set": bool(
                manifest.get("independent_validation_set", False)
            ),
            "independent_final_test": bool(
                manifest.get("independent_final_test", False)
            ),
            "selection_protocol": str(
                manifest.get("selection_protocol") or "same-task gate keep/revert"
            ),
            "optimizer_model": manifest.get("optimizer_model"),
            "candidate_gate_model": manifest.get("candidate_gate_model"),
            "selected_result_model_counts": dict(
                Counter(str(row["selected_result_model"]) for row in statuses)
            ),
            "selected_original_baseline_after_revert_count": sum(
                row["selected_original_baseline_after_revert"] is True
                for row in statuses
            ),
            "tasks": statuses,
        },
    )
    write_json(
        output / "evidence_index.json",
        {
            "schema_version": "skillopt-composite-evidence-index-v1",
            "repository_root": ".",
            "raw_runs": [
                {
                    **row,
                    "root": f"experiments/{row['run_id']}",
                    "metadata": f"experiments/{row['run_id']}/metadata.json"
                    if (ROOT / "experiments" / row["run_id"] / "metadata.json").exists()
                    else None,
                    "commands": f"experiments/{row['run_id']}/commands"
                    if (ROOT / "experiments" / row["run_id"] / "commands").exists()
                    else None,
                    "code_snapshot": f"experiments/{row['run_id']}/code"
                    if (ROOT / "experiments" / row["run_id"] / "code").exists()
                    else None,
                    "terminal_logs": f"experiments/{row['run_id']}/terminal_logs"
                    if (ROOT / "experiments" / row["run_id"] / "terminal_logs").exists()
                    else None,
                }
                for row in (manifest.get("raw_runs") or [])
            ],
            "tasks": evidence,
        },
    )
    write_json(
        output / "experiment_manifest.json",
        {
            **manifest,
            "generated_at": datetime.now(UTC).isoformat(),
            "manifest_source": relative(manifest_path),
        },
    )

    with (output / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0]))
        writer.writeheader()
        writer.writerows(summary_rows)

    passed_count = sum(row["task_passed"] == "true" for row in summary_rows)
    failed_count = len(summary_rows) - passed_count
    invalid_count = sum(int(row["invalid_gate_attempts"]) for row in summary_rows)
    (output / "summary.md").write_text(
        "\n".join(
            [
                f"# {manifest.get('composite_id', 'SkillOpt composite')} summary",
                "",
                f"- Tasks: {len(summary_rows)}",
                f"- Healthy and comparable: {len(summary_rows)}",
                f"- Passed: {passed_count}",
                f"- Failed: {failed_count}",
                f"- Invalid gate attempts in selected repair loops: {invalid_count}",
                f"- Preserved superseded invalid runs: {len(manifest.get('superseded_invalid_runs') or [])}",
                "- Selection: same-task keep/revert gate",
                "- Independent validation set: no",
                "- Independent final test set: no",
                "",
            ]
        ),
        encoding="utf-8",
    )

    (output / "EVIDENCE_GUIDE.md").write_text(
        "\n".join(
            [
                "# Evidence guide",
                "",
                "`submission.json` is the evaluator-facing file. Each repaired Skill bundle is under `tasks/<task>/skills/`.",
                "",
                f"`summary.csv` and `run_status.json` contain the selected score, health classification, rounds, decisions, and source run for all {len(summary_rows)} tasks.",
                "",
                "`evidence_index.json` maps every selected task to its immutable raw method directory, repair loop, baseline, source task, terminal logs, and all valid or invalid rollout job directories. Those raw directories contain optimizer inputs and full replies, diagnosis samples, candidate Skill packages, gate results, executor trajectories, verifier stdout/results, and keep/revert reasons.",
                "",
                (
                    "The experiment did not create an independent validation split or independent final-test split. "
                    + (
                        "Tasks listed in `final_result_run_overrides` use a separate execution of the frozen selected Skill for the reported score, but it still uses the same task inputs and is not held out. "
                        if manifest.get("final_result_run_overrides")
                        else "Candidate acceptance and the reported score both use the same task gate. "
                    )
                    + "This limitation is recorded explicitly rather than inferred as held-out evaluation."
                    if not manifest.get("independent_validation_set")
                    and not manifest.get("independent_final_test")
                    else "Train/validation/final-test split declarations are recorded in experiment_manifest.json and run_status.json."
                ),
                "",
                *[str(note) for note in (manifest.get("provenance_notes") or [])],
                "" if manifest.get("provenance_notes") else "",
            ]
        ),
        encoding="utf-8",
    )

    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
