"""Guards the published Gold subset from implementation commit 8393b98e576a3fc5cf542c663e18cfea6bbd6701."""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.scripts.evaluate_skill_diagnosis_repair import load_inputs


def test_published_core25_gold_contains_exactly_the_seven_curated_tasks(
    tmp_path: Path,
) -> None:
    gold_path = Path(__file__).resolve().parents[1] / "data" / "core25" / "gold.json"
    published = json.loads(gold_path.read_text(encoding="utf-8-sig"))
    expected_defect_counts = {
        "dialogue-parser": 1,
        "exoplanet-detection-period": 1,
        "python-scala-translation": 3,
        "sec-financial-report": 3,
        "paratransit-routing": 2,
        "software-dependency-audit": 1,
        "video-silence-remover": 3,
    }
    submission_path = tmp_path / "submission.json"
    submission_path.write_text(
        json.dumps(
            {
                "method_id": "offline-release-check",
                "benchmark_version": published["benchmark_version"],
                "tasks": [
                    {"task_id": task_id, "diagnoses": [], "repaired_bundle": task_id}
                    for task_id in expected_defect_counts
                ],
            }
        ),
        encoding="utf-8",
    )

    loaded_gold, _, gold_tasks, submitted_tasks = load_inputs(
        gold_path, submission_path
    )

    assert loaded_gold == published
    assert set(gold_tasks) == set(submitted_tasks) == set(expected_defect_counts)
    assert {
        task_id: len(task["defects"]) for task_id, task in gold_tasks.items()
    } == expected_defect_counts
    assert sum(len(task["defects"]) for task in gold_tasks.values()) == 14
    for task in gold_tasks.values():
        original = gold_path.parent / task["original_bundle"]
        assert original.is_dir()
        assert task["task_context"].strip()
        for defect in task["defects"]:
            for location in defect["locations"]:
                assert (original / location["file"]).is_file()
