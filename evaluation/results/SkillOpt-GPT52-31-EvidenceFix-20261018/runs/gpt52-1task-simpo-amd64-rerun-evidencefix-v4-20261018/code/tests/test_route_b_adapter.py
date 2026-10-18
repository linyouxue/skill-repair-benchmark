from __future__ import annotations

from pathlib import Path

from adapters.common.rewrite_engine import (
    build_suggestion,
    infer_run_id_from_workspace,
    shared_diagnosis_dir,
)


def test_build_suggestion_is_method_neutral() -> None:
    common = dict(
        task_id="demo-task",
        skill_rel=Path("foo/SKILL.md"),
        task_context="task ctx",
        baseline_source_type="failure",
        baseline_context="baseline ctx",
        diagnosis_item={
            "confidence": "0.9",
            "diagnosis": "missing recipe",
            "repair_instruction": "add concrete checks",
        },
    )
    so = build_suggestion(**common, method_name="skillopt")
    lite = build_suggestion(**common, method_name="skillopt-lite")
    assert so == lite
    assert "SkillOpt style" not in so["instruction"]
    assert "SkillOpt-Lite style" not in so["instruction"]
    assert "add concrete checks" in so["instruction"]


def test_infer_run_id_and_shared_dir(tmp_path: Path) -> None:
    workspace = tmp_path / "experiments" / "run-abc" / "methods" / "skillopt" / "task-x" / "workspace"
    workspace.mkdir(parents=True)
    assert infer_run_id_from_workspace(workspace) == "run-abc"
    so = shared_diagnosis_dir("run-abc", "task-x", method_name="skillopt")
    lite = shared_diagnosis_dir("run-abc", "task-x", method_name="skillopt-lite")
    assert so.name == "skillopt"
    assert so.parent.name == "round_1"
    assert so.parent.parent.name == "task-x"
    assert lite.name == "skillopt-lite"
    assert so != lite
