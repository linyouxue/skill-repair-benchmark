from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.scripts.export_causalflow_submission import (
    ExportError,
    export_submission,
    main,
)


def _json(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _inputs(tmp_path: Path, diagnosis: dict) -> tuple[Path, Path, Path]:
    template = _json(
        tmp_path / "template.json",
        {
            "benchmark_version": "test-v1",
            "tasks": [{"task_id": "task-a"}],
        },
    )
    result = _json(tmp_path / "result.json", diagnosis)
    bundle = tmp_path / "final-skills" / "skill-a"
    bundle.mkdir(parents=True)
    (bundle / "SKILL.md").write_text("# Skill\nFixed rule.\n", encoding="utf-8")
    (bundle / "helper.py").write_text("VALUE = 1\n", encoding="utf-8")
    plan = _json(
        tmp_path / "plan.json",
        {
            "method_id": "causalflow",
            "benchmark_version": "test-v1",
            "tasks": [
                {
                    "task_id": "task-a",
                    "diagnosis_result": result.name,
                    "final_bundle": "final-skills",
                    "executor_run_id": "task-a-final-r0",
                }
            ],
        },
    )
    return plan, template, bundle.parent


def test_exports_prediction_and_complete_bundle(tmp_path: Path) -> None:
    plan, template, bundle = _inputs(
        tmp_path,
        {
            "method_id": "causalflow",
            "task_id": "task-a",
            "predictions": [
                {
                    "file": "skill-a/SKILL.md",
                    "start_line": 2,
                    "end_line": 2,
                    "explanation": "The rule omits a required check.",
                }
            ],
        },
    )

    report = export_submission(plan, template, tmp_path / "output")

    submission = json.loads(Path(report["submission"]).read_text(encoding="utf-8"))
    assert submission == {
        "method_id": "causalflow",
        "benchmark_version": "test-v1",
        "tasks": [
            {
                "task_id": "task-a",
                "diagnoses": [
                    {
                        "prediction_id": "P1",
                        "description": "The rule omits a required check.",
                        "locations": [
                            {
                                "file": "skill-a/SKILL.md",
                                "start_line": 2,
                                "end_line": 2,
                            }
                        ],
                    }
                ],
                "repaired_bundle": "tasks/task-a/skills",
                "executor_run_id": "task-a-final-r0",
            }
        ],
    }
    copied = tmp_path / "output" / "tasks" / "task-a" / "skills"
    assert (copied / "skill-a" / "SKILL.md").read_bytes() == (
        bundle / "skill-a" / "SKILL.md"
    ).read_bytes()
    assert (copied / "skill-a" / "helper.py").read_bytes() == (
        bundle / "skill-a" / "helper.py"
    ).read_bytes()
    assert report["tasks"][0]["bundle_file_count"] == 2


def test_action_level_result_is_not_mislabeled_as_skill_repair(tmp_path: Path) -> None:
    plan, template, _ = _inputs(
        tmp_path,
        {
            "task": "task-a",
            "strict_baseline_replay_matches": True,
            "causal_attribution": {"causal_steps": [3]},
            "counterfactual_repair": {"3": [{"repaired_text": "new command"}]},
            "summary": {"causal_steps": 1},
        },
    )

    report = export_submission(plan, template, tmp_path / "output")

    submission = json.loads(Path(report["submission"]).read_text(encoding="utf-8"))
    assert submission["tasks"][0]["diagnoses"] == []
    assert report["tasks"][0]["warnings"] == [
        "action_level_crs_has_no_explicit_skill_diagnosis",
        "action_level_repairs_do_not_modify_skill_bundle",
    ]


def test_rejects_invalid_replay_and_does_not_create_output(tmp_path: Path) -> None:
    plan, template, _ = _inputs(
        tmp_path,
        {
            "status": "invalid_baseline_replay",
            "causal_attribution": {},
        },
    )

    with pytest.raises(ExportError, match="invalid baseline replay"):
        export_submission(plan, template, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_rejects_links_and_existing_output(tmp_path: Path) -> None:
    plan, template, bundle = _inputs(tmp_path, {"diagnoses": []})
    (bundle / "skill-a" / "link.py").symlink_to(bundle / "skill-a" / "helper.py")

    with pytest.raises(ExportError, match="contains a link"):
        export_submission(plan, template, tmp_path / "output")
    assert not (tmp_path / "output").exists()

    (bundle / "skill-a" / "link.py").unlink()
    (tmp_path / "output").mkdir()
    with pytest.raises(ExportError, match="refusing to overwrite"):
        export_submission(plan, template, tmp_path / "output")


def test_rejects_version_and_task_set_mismatch(tmp_path: Path) -> None:
    plan, template, _ = _inputs(tmp_path, {"diagnoses": []})
    value = json.loads(plan.read_text(encoding="utf-8"))
    value["benchmark_version"] = "wrong"
    _json(plan, value)
    with pytest.raises(ExportError, match="benchmark_version"):
        export_submission(plan, template, tmp_path / "output")

    value["benchmark_version"] = "test-v1"
    value["tasks"][0]["task_id"] = "other-task"
    _json(plan, value)
    with pytest.raises(ExportError, match="exactly the template task IDs"):
        export_submission(plan, template, tmp_path / "output")


def test_rejects_task_id_path_traversal(tmp_path: Path) -> None:
    plan, template, _ = _inputs(tmp_path, {"diagnoses": []})
    value = json.loads(template.read_text(encoding="utf-8"))
    value["tasks"][0]["task_id"] = "../outside"
    _json(template, value)

    with pytest.raises(ExportError, match="one path component"):
        export_submission(plan, template, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_original_pass_requires_explicit_run_and_omits_bundle(tmp_path: Path) -> None:
    plan, template, _ = _inputs(tmp_path, {"diagnoses": []})
    value = json.loads(plan.read_text(encoding="utf-8"))
    value["tasks"][0] = {
        "task_id": "task-a",
        "original_pass": True,
        "original_run_id": "task-a-original-r0",
    }
    _json(plan, value)

    report = export_submission(plan, template, tmp_path / "output")

    submission = json.loads(Path(report["submission"]).read_text(encoding="utf-8"))
    assert submission["tasks"] == [
        {
            "task_id": "task-a",
            "original_pass": True,
            "original_run_id": "task-a-original-r0",
        }
    ]
    assert not (tmp_path / "output" / "tasks").exists()


def test_core25_plan_template_matches_shared_task_set() -> None:
    evaluation = Path(__file__).resolve().parents[1]
    shared = evaluation / "data" / "core25" / "submission.template.json"
    plan = json.loads(
        (evaluation / "data" / "core25" / "causalflow_plan.template.json").read_text(
            encoding="utf-8"
        )
    )
    template = json.loads(shared.read_text(encoding="utf-8"))

    assert plan["benchmark_version"] == template["benchmark_version"]
    assert [row["task_id"] for row in plan["tasks"]] == [
        row["task_id"] for row in template["tasks"]
    ]


def test_shared_evaluator_accepts_exported_submission(tmp_path: Path) -> None:
    evaluation = Path(__file__).resolve().parents[1]
    script = evaluation / "scripts" / "evaluate_skill_diagnosis_repair.py"
    diagnosis = _json(tmp_path / "diagnosis.json", {"diagnoses": []})
    plan = _json(
        tmp_path / "plan.json",
        {
            "method_id": "causalflow-test",
            "benchmark_version": "v1",
            "tasks": [
                {
                    "task_id": "example-task",
                    "diagnosis_result": str(diagnosis),
                    "final_bundle": str(
                        evaluation / "examples" / "original" / "skills"
                    ),
                }
            ],
        },
    )
    output = tmp_path / "output"

    code = main(
        [
            "--plan",
            str(plan),
            "--template",
            str(evaluation / "examples" / "submission.json"),
            "--output",
            str(output),
            "--evaluator-script",
            str(script),
            "--gold",
            str(evaluation / "examples" / "gold.json"),
        ]
    )

    assert code == 0
    summary = json.loads(
        (output / "evaluation-output" / "summary.json").read_text(encoding="utf-8")
    )
    assert summary["status"] == "dry_run"
    assert summary["maximum_judge_requests"] == 2


def test_shared_evaluator_scores_supplied_responses(tmp_path: Path) -> None:
    evaluation = Path(__file__).resolve().parents[1]
    script = evaluation / "scripts" / "evaluate_skill_diagnosis_repair.py"
    example = evaluation / "examples"
    example_submission = json.loads(
        (example / "submission.json").read_text(encoding="utf-8")
    )
    diagnosis = _json(
        tmp_path / "diagnosis.json",
        {"diagnoses": example_submission["tasks"][0]["diagnoses"]},
    )
    plan = _json(
        tmp_path / "plan.json",
        {
            "method_id": "method_a",
            "benchmark_version": "v1",
            "tasks": [
                {
                    "task_id": "example-task",
                    "diagnosis_result": str(diagnosis),
                    "final_bundle": str(example / "repaired" / "skills"),
                }
            ],
        },
    )
    output = tmp_path / "output"

    code = main(
        [
            "--plan",
            str(plan),
            "--template",
            str(example / "submission.json"),
            "--output",
            str(output),
            "--evaluator-script",
            str(script),
            "--gold",
            str(example / "gold.json"),
            "--evaluation-mode",
            "responses",
            "--judge-responses",
            str(example / "judge_responses.json"),
        ]
    )

    assert code == 0
    summary = json.loads(
        (output / "evaluation-output" / "summary.json").read_text(encoding="utf-8")
    )
    assert summary["status"] == "complete"
    assert summary["metrics"]["diagnosis"]["f1"] == pytest.approx(2 / 3)
    assert summary["metrics"]["repair"]["f1"] == pytest.approx(1 / 3)
    assert summary["metrics"]["location_accuracy"] == 1.0
