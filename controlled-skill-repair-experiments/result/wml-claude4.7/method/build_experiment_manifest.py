#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path


ROOT = Path(os.environ.get("WML_CONTROLLED_ROOT", Path(__file__).resolve().parent.parent))


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def relative(path: str | Path) -> str:
    return Path(path).resolve().relative_to(ROOT).as_posix()


def prepared_record(folder: str, experiment_id: str) -> dict:
    return load(ROOT / folder / experiment_id / "RUN.json")


def entry(kind: str, experiment_id: str, row: dict, prepared_folder: str) -> dict:
    record = prepared_record(prepared_folder, experiment_id)
    attempt_dir = Path(row["attempt_dir"]).resolve()
    audit_path = attempt_dir / "EXECUTION_AUDIT.json"
    preflight_path = attempt_dir / "EXECUTION_PREFLIGHT.json"
    if not audit_path.is_file() or not preflight_path.is_file():
        raise RuntimeError(f"missing environment/Skill audit for {experiment_id}")
    audit = load(audit_path)
    preflight = load(preflight_path)
    if audit.get("valid") is not True:
        raise RuntimeError(f"failed environment/Skill audit for {experiment_id}")
    if preflight.get("task_id") != record["task_id"]:
        raise RuntimeError(f"task identity mismatch for {experiment_id}")
    collision_guard = preflight.get("collision_guard") or {}
    if collision_guard.get("enabled") is not True:
        raise RuntimeError(f"environment collision guard missing for {experiment_id}")
    result_file = relative(row["result_file"])
    result_path = ROOT / result_file
    trajectory = result_path.parent / "trajectory" / "acp_trajectory.jsonl"
    if not trajectory.is_file() or trajectory.stat().st_size == 0:
        raise RuntimeError(f"missing trajectory for {experiment_id}")
    return {
        "experiment_type": kind,
        "experiment_id": experiment_id,
        "task_id": record["task_id"],
        "trial_id": record.get("trial_id"),
        "dataset": record.get("dataset"),
        "condition": record.get("condition"),
        "status": row["status"],
        "reward": row["reward"],
        "prepared_dir": f"{prepared_folder}/{experiment_id}",
        "attempt_dir": relative(row["attempt_dir"]),
        "result_file": result_file,
        "trajectory_file": trajectory.relative_to(ROOT).as_posix(),
        "execution_preflight": relative(preflight_path),
        "execution_audit": relative(audit_path),
        "unique_task_name": preflight["unique_task_name"],
        "task_identity_sha256": preflight["task_identity_sha256"],
        "dockerfile_sha256": preflight.get("dockerfile_sha256"),
        "skill_bundle_sha256": audit["expected_skill_bundle"]["skill_bundle_sha256"],
        "skill_exposure_verified": True,
        "environment_collision_guard_verified": True,
    }


def main() -> None:
    repairs = load(ROOT / "eval_summary.json")
    controls = load(ROOT / "control_eval_summary.json")
    if (repairs["total"], repairs["valid"], repairs["invalid"]) != (22, 22, 0):
        raise RuntimeError("WML repair summary is incomplete")
    if (controls["total"], controls["valid"], controls["invalid"]) != (33, 33, 0):
        raise RuntimeError("control summary is incomplete")
    if repairs["executor_model"] != controls["executor_model"]:
        raise RuntimeError("repair/control executor model mismatch")
    if repairs["base_url"] != controls["base_url"]:
        raise RuntimeError("repair/control base URL mismatch")

    experiments = []
    for row in repairs["trials"]:
        item = entry("wml_repair", row["trial_id"], row, "prepared")
        item["input_dir"] = f"inputs/{row['trial_id']}"
        item["candidate_dir"] = f"candidates/{row['trial_id']}"
        experiments.append(item)
    for row in controls["controls"]:
        experiments.append(entry("control", row["control_id"], row, "control-prepared"))

    if len(experiments) != 55 or len({item["experiment_id"] for item in experiments}) != 55:
        raise RuntimeError("expected 55 unique experiments")
    output = {
        "schema_version": 1,
        "experiment_id": "WML-Paratera-Claude47-Controlled-55-20261031",
        "repair_method": "workflow-localized-mechanism-learning",
        "repair_model": "Claude-Opus-4.7",
        "executor_agent": "openhands",
        "executor_model": repairs["executor_model"],
        "base_url": repairs["base_url"],
        "counts": {
            "total": 55,
            "wml_repairs": 22,
            "controls": 33,
            "valid": 55,
            "invalid": 0,
            "passes": repairs["passes"] + controls["passes"],
            "failures": repairs["failures"] + controls["failures"],
        },
        "experiments": experiments,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    (ROOT / "experiment-manifest-55.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
