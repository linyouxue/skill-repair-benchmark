#!/usr/bin/env python3
"""Build the organizer-style scorecard from audited results and semantic review."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional


WORKSPACE = Path("/Users/elsie/Desktop/SkillOpt-eva")
RUN = WORKSPACE / "experiments/gpt52-skillopt-controlled-location-single-r2l5-v2-20261027"
PACKAGE = WORKSPACE / "skill-repair-controlled-datasets-20261020"

FIELDS = [
    "experiment_id", "dataset", "task_id", "trial_id", "condition",
    "heldout_repair_id", "method", "repair_model", "executor_agent",
    "executor_model", "seed", "repair_budget", "executor_budget",
    "candidate_sha256", "positive_control_passed",
    "condition_baseline_passed", "native_task_passed", "native_reward",
    "target_semantically_repaired", "non_target_gold_preserved",
    "evidence_path", "reviewer", "notes",
]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def selected_reward(selected: dict[str, Any], unit: str) -> Optional[float]:
    value = selected.get(unit)
    return value.get("reward") if isinstance(value, dict) else None


def boolean_text(value: Optional[bool]) -> str:
    if value is None:
        return ""
    return "true" if value else "false"


def complete_candidate(trial: dict[str, Any]) -> Path:
    root = RUN / "candidates" / trial["dataset"] / trial["trial_id"]
    candidates = sorted(path.parent for path in root.glob("attempt-*/CANDIDATE_SHA256.json"))
    if len(candidates) != 1:
        raise RuntimeError(f"Expected one complete candidate for {trial['trial_id']}")
    return candidates[0]


def baseline_unit(trial: dict[str, Any]) -> str:
    if trial["dataset"] == "location":
        return f"original/{trial['task_id']}"
    if trial["condition"] == "all_faults":
        return f"all_faults/{trial['task_id']}"
    return f"condition_baseline/{trial['trial_id']}"


def aggregate(rows: list[dict[str, Any]], controls: dict[str, Any]) -> dict[str, Any]:
    groups: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {
            "trials": 0,
            "native_passes": 0,
            "native_reward_sum": 0.0,
            "semantic_repairs": 0,
            "semantic_partial": 0,
            "non_target_preserved": 0,
            "non_target_reviewed": 0,
        }
    )
    for row in rows:
        key = (row["dataset"], row["condition"])
        group = groups[key]
        group["trials"] += 1
        reward = float(row["native_reward"])
        group["native_reward_sum"] += reward
        group["native_passes"] += reward == 1.0
        group["semantic_repairs"] += row["target_semantically_repaired"] == "true"
        group["semantic_partial"] += row["target_repair_assessment"] == "partial"
        if row["non_target_gold_preserved"]:
            group["non_target_reviewed"] += 1
            group["non_target_preserved"] += row["non_target_gold_preserved"] == "true"
    serializable_groups = []
    for (dataset, condition), group in sorted(groups.items()):
        count = group["trials"]
        group.update({
            "dataset": dataset,
            "condition": condition,
            "native_pass_rate": group["native_passes"] / count,
            "mean_native_reward": group.pop("native_reward_sum") / count,
            "semantic_repair_rate": group["semantic_repairs"] / count,
        })
        serializable_groups.append(group)
    control_groups: dict[str, list[float]] = defaultdict(list)
    for unit, value in controls.items():
        if "/" not in unit:
            continue
        condition = unit.split("/", 1)[0]
        if condition in {"full_gold", "original", "all_faults", "condition_baseline"}:
            control_groups[condition].append(float(value["reward"]))
    return {
        "schema_version": 1,
        "experiment_id": RUN.name,
        "trial_count": len(rows),
        "native_passes": sum(row["native_task_passed"] == "true" for row in rows),
        "semantic_repairs": sum(row["target_semantically_repaired"] == "true" for row in rows),
        "groups": serializable_groups,
        "controls_completed": {
            condition: {
                "valid_runs": len(rewards),
                "passes": sum(reward == 1.0 for reward in rewards),
                "mean_reward": sum(rewards) / len(rewards),
            }
            for condition, rewards in sorted(control_groups.items())
        },
    }


def main() -> None:
    catalog = read_json(PACKAGE / "datasets/catalog.json")
    configured = {
        line.strip()
        for line in (RUN / "configs/trials.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    result_audit = read_json(RUN / "summaries/result-audit.json")
    selected = result_audit["selected"]
    semantic = {
        row["trial_id"]: row
        for row in read_json(RUN / "summaries/semantic-review.json")["trials"]
    }
    rows: list[dict[str, Any]] = []
    for trial in catalog["trials"]:
        trial_id = trial["trial_id"]
        if trial_id not in configured:
            continue
        if trial_id not in selected:
            raise RuntimeError(f"Missing valid repaired result for {trial_id}")
        review = semantic[trial_id]
        candidate = complete_candidate(trial)
        response = read_json(candidate / "response.json")
        native_reward = float(selected[trial_id]["reward"])
        positive_reward = selected_reward(selected, f"full_gold/{trial['task_id']}")
        baseline = baseline_unit(trial)
        baseline_reward = selected_reward(selected, baseline)
        evidence = [
            selected[trial_id]["result"],
            (candidate / "response.json").relative_to(RUN).as_posix(),
            "summaries/semantic-review.json",
        ]
        row = {
            "experiment_id": RUN.name,
            "dataset": trial["dataset"],
            "task_id": trial["task_id"],
            "trial_id": trial_id,
            "condition": trial["condition"],
            "heldout_repair_id": ";".join(trial["target_repair_ids"]),
            "method": "skillopt-controlled-oracle-hint-r2l5-v2",
            "repair_model": "openai/gpt-5.2",
            "executor_agent": "openhands",
            "executor_model": "ai360/openai/gpt-5.2",
            "seed": "unset",
            "repair_budget": "N=3;L=5/file;R=2;same-task-gate=false",
            "executor_budget": "max-parent-iterations=60;loop=single-shot",
            "candidate_sha256": response["candidate_bundle_sha256"],
            "positive_control_passed": boolean_text(
                None if positive_reward is None else positive_reward == 1.0
            ),
            "condition_baseline_passed": boolean_text(
                None if baseline_reward is None else baseline_reward == 1.0
            ),
            "native_task_passed": boolean_text(native_reward == 1.0),
            "native_reward": native_reward,
            "target_semantically_repaired": boolean_text(review["target_semantically_repaired"]),
            "non_target_gold_preserved": boolean_text(review["non_target_gold_preserved"]),
            "evidence_path": ";".join(evidence),
            "reviewer": "codex-gpt52-window",
            "notes": review["notes"],
            # Internal aggregation field; omitted from CSV by FIELDS.
            "target_repair_assessment": review["target_repair_assessment"],
        }
        rows.append(row)

    out = RUN / "summaries/scorecard.csv"
    with out.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    summary = aggregate(rows, selected)
    (RUN / "summaries/metrics-summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
