#!/usr/bin/env python3
"""Fail-closed structural audit for a composite SkillOpt submission."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def fail(message: str) -> None:
    raise RuntimeError(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("submission_dir", type=Path)
    args = parser.parse_args()
    output = args.submission_dir.resolve()

    submission = read_object(output / "submission.json")
    status = read_object(output / "run_status.json")
    evidence = read_object(output / "evidence_index.json")
    manifest = read_object(output / "experiment_manifest.json")
    expected = [
        line.strip()
        for line in (ROOT / str(manifest["task_list"]))
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    submitted = [str(row["task_id"]) for row in submission.get("tasks") or []]
    status_ids = [str(row["task_id"]) for row in status.get("tasks") or []]
    evidence_ids = [str(row["task_id"]) for row in evidence.get("tasks") or []]
    if submitted != expected or status_ids != expected or evidence_ids != expected:
        fail("task order/content differs between tasks.txt and composite records")
    if len(set(expected)) != len(expected):
        fail("duplicate task id")
    if status.get("task_count") != len(expected):
        fail("run_status task_count mismatch")
    if status.get("healthy_count") != len(expected):
        fail("not every selected result is healthy")
    if status.get("comparable_count") != len(expected):
        fail("not every selected result is comparable")

    status_by_task = {str(row["task_id"]): row for row in status["tasks"]}
    evidence_by_task = {str(row["task_id"]): row for row in evidence["tasks"]}
    gate_result_count = 0
    for row in submission["tasks"]:
        task_id = str(row["task_id"])
        bundle = output / str(row["repaired_bundle"])
        if not bundle.is_dir() or not list(bundle.rglob("SKILL.md")):
            fail(f"missing repaired Skill bundle: {task_id}")
        compact = output / "selected_results" / task_id
        result = read_object(compact / "method_result.json")
        read_object(compact / "repair_loop.json")
        if result.get("task_id") != task_id:
            fail(f"method_result task mismatch: {task_id}")
        if result.get("rollout_id") != row.get("executor_run_id"):
            fail(f"executor run id mismatch: {task_id}")
        if result.get("comparable") is not True or result.get("execution_ok") is not True:
            fail(f"selected result is not comparable/execution_ok: {task_id}")
        task_status = status_by_task[task_id]
        if task_status.get("healthy") is not True:
            fail(f"selected task is unhealthy: {task_id}")

        task_evidence = evidence_by_task[task_id]
        for field in (
            "method_result",
            "repair_loop",
            "method_workspace",
            "before_skill",
            "best_skill",
        ):
            path = ROOT / str(task_evidence[field])
            if not path.exists():
                fail(f"missing evidence path for {task_id}/{field}: {path}")
        for field in (
            "source_task",
            "baseline",
            "run_metadata",
            "run_commands",
            "code_snapshot",
        ):
            value = task_evidence.get(field)
            if value is not None and not (ROOT / str(value)).exists():
                path = ROOT / str(value)
                fail(f"missing evidence path for {task_id}/{field}: {path}")
        for rollout in task_evidence.get("rollouts") or []:
            if rollout.get("rollout_dir") and not (
                ROOT / str(rollout["rollout_dir"])
            ).is_dir():
                fail(f"missing rollout dir: {task_id}/{rollout.get('rollout_id')}")
            if rollout.get("attempt_record") and not (
                ROOT / str(rollout["attempt_record"])
            ).is_file():
                fail(f"missing gate attempt record: {task_id}")
        workspace = ROOT / str(task_evidence["method_workspace"])
        allowed_gate_models = set(manifest.get("candidate_gate_model_ids") or [])
        allowed_gate_routes = set(
            manifest.get("candidate_gate_provider_routes") or []
        )
        for gate_path in sorted(workspace.glob("round_*/gate_result.json")):
            gate = read_object(gate_path)
            gate_result_count += 1
            if allowed_gate_models and gate.get("model") not in allowed_gate_models:
                fail(f"unexpected candidate gate model: {gate_path}")
            if allowed_gate_routes and gate.get("provider_route") not in allowed_gate_routes:
                fail(f"unexpected candidate gate provider: {gate_path}")
        for log_path in task_evidence.get("terminal_logs") or []:
            if not (ROOT / str(log_path)).is_file():
                fail(f"missing terminal log: {task_id}/{log_path}")

    print(
        json.dumps(
            {
                "valid": True,
                "task_count": len(expected),
                "passed": status.get("passed_count"),
                "failed": status.get("failed_count"),
                "invalid_gate_attempts_preserved": status.get(
                    "invalid_gate_attempts_preserved"
                ),
                "superseded_invalid_runs_preserved": len(
                    status.get("superseded_invalid_runs_preserved") or []
                ),
                "candidate_gate_results": gate_result_count,
                "candidate_gate_model": status.get("candidate_gate_model"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
