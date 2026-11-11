#!/usr/bin/env python3
"""Prepare the 33 fixed control conditions from the controlled dataset."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(os.environ.get("CONTROL_WORK_ROOT", Path(__file__).resolve().parent.parent))
PREPARED = ROOT / "control-prepared"
PACKAGE = Path("/Users/king/Downloads/skill-repair-controlled-datasets-20261020")
RUNNER = PACKAGE / "tools" / "runner.py"

TASKS = [
    "dialogue-parser",
    "data-to-d3",
    "flink-query",
    "manufacturing-equipment-maintenance",
    "pddl-airport-planning",
    "video-silence-remover",
    "sec-financial-report",
    "fix-build-google-auto",
]

LEAVE_ONE_OUT = {
    "flink-query": ["single-flink-query-RI-001", "single-flink-query-RI-002"],
    "manufacturing-equipment-maintenance": [
        "single-manufacturing-equipment-maintenance-RI-001",
        "single-manufacturing-equipment-maintenance-RI-002",
    ],
    "sec-financial-report": [
        "single-sec-financial-report-RI-001",
        "single-sec-financial-report-RI-002",
        "single-sec-financial-report-RI-003",
    ],
    "video-silence-remover": [
        "single-video-silence-remover-RI-001",
        "single-video-silence-remover-RI-002",
        "single-video-silence-remover-RI-003",
    ],
    "fix-build-google-auto": [
        "single-fix-build-google-auto-RI-001",
        "single-fix-build-google-auto-RI-002",
    ],
}


def specs() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for task in TASKS:
        for condition in ("full_gold", "original"):
            rows.append({
                "control_id": f"{task}__{condition}",
                "task": task,
                "condition": condition,
            })
    for task, trials in LEAVE_ONE_OUT.items():
        rows.append({
            "control_id": f"{task}__all_faults",
            "task": task,
            "condition": "all_faults",
        })
        for trial in trials:
            rows.append({
                "control_id": f"{trial}__condition_baseline",
                "task": task,
                "trial": trial,
                "condition": "condition_baseline",
            })
    return rows


def main() -> int:
    rows = specs()
    if len(rows) != 33:
        raise RuntimeError(f"expected 33 controls, got {len(rows)}")
    PREPARED.mkdir(parents=True, exist_ok=True)
    for index, row in enumerate(rows, 1):
        destination = PREPARED / row["control_id"]
        if (destination / "RUN.json").is_file() and (destination / "PREPARED_SHA256.json").is_file():
            print(f"SKIP {index:02d}/33 {row['control_id']}", flush=True)
            continue
        command = [
            sys.executable,
            str(RUNNER),
            "control",
            "--task",
            row["task"],
            "--condition",
            row["condition"],
            "--out",
            str(destination),
        ]
        if row.get("trial"):
            command.extend(["--trial", row["trial"]])
        subprocess.run(command, check=True)
        print(f"READY {index:02d}/33 {row['control_id']}", flush=True)
    (ROOT / "control_manifest.json").write_text(
        json.dumps({"total": len(rows), "controls": rows}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
