#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def relative(path: str | Path) -> str:
    return Path(path).resolve().relative_to(ROOT).as_posix()


def prepared_record(folder: str, experiment_id: str) -> dict:
    return load(ROOT / folder / experiment_id / "RUN.json")


def entry(kind: str, experiment_id: str, row: dict, prepared_folder: str) -> dict:
    record = prepared_record(prepared_folder, experiment_id)
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
    }


def main() -> None:
    repairs = load(ROOT / "eval_summary.json")
    controls = load(ROOT / "control_eval_summary.json")
    if (repairs["total"], repairs["valid"], repairs["invalid"]) != (22, 22, 0):
        raise RuntimeError("WML repair summary is incomplete")
    if (controls["total"], controls["valid"], controls["invalid"]) != (33, 33, 0):
        raise RuntimeError("control summary is incomplete")

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
        "executor_model": "openai/Claude-Opus-4.7",
        "base_url": "https://llmapi.paratera.com/v1",
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
