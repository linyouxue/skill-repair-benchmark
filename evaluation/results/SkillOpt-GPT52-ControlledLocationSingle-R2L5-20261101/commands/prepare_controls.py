#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path("/Users/elsie/Desktop/SkillOpt-eva")
RUN = ROOT / "experiments/gpt52-skillopt-controlled-location-single-r2l5-v2-20261027"
PACKAGE = ROOT / "skill-repair-controlled-datasets-20261020"
RUNNER = PACKAGE / "tools/runner.py"
catalog = json.loads((PACKAGE / "datasets/catalog.json").read_text())


def call(args: list[str], out: Path) -> None:
    if (out / "PREPARED_SHA256.json").is_file():
        return
    subprocess.run([sys.executable, "-B", str(RUNNER), "control", *args, "--out", str(out)], check=True)


for task in catalog["tasks"]:
    task_id = task["task_id"]
    call(["--task", task_id, "--condition", "full_gold"], RUN / "prepared/controls/full_gold" / task_id)
    call(["--task", task_id, "--condition", "original"], RUN / "prepared/controls/original" / task_id)
    if task.get("all_faults_skills"):
        call(["--task", task_id, "--condition", "all_faults"], RUN / "prepared/controls/all_faults" / task_id)

for trial in catalog["trials"]:
    if trial["condition"] != "leave_one_out":
        continue
    trial_id = trial["trial_id"]
    call(
        ["--task", trial["task_id"], "--condition", "condition_baseline", "--trial", trial_id],
        RUN / "prepared/controls/condition_baseline" / trial_id,
    )

