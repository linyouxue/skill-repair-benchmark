from __future__ import annotations

from pathlib import Path

from adapters.common.rewrite_engine import (
    _load_jpg_diagnosis_packet,
    _messages_for_tatu,
    build_suggestion,
    infer_run_id_from_workspace,
    shared_diagnosis_dir,
)
from adapters.common.paths import task_dir


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


def test_jpg_package_routes_to_published_field_verifier() -> None:
    """Guards JPG integration commit 4be9a173: do not fall back to the old task."""
    task = task_dir("jpg-ocr-stat")
    assert (task / "diagnosis" / "index.json").is_file()
    assert (task / "verifier" / "score_accuracy.py").is_file()
    assert (task / "verifier" / "write_reward.py").is_file()


def test_jpg_packet_contains_22_images_and_tatu_transport_keeps_pixels() -> None:
    """Guards JPG integration commit 4be9a173: diagnosis sends real images."""
    packet = _load_jpg_diagnosis_packet("w0001")
    blocks = packet["messages"][0]["content"]
    assert sum(block.get("type") == "image_url" for block in blocks) == 22

    converted = _messages_for_tatu(packet["messages"])
    converted_blocks = converted[0]["content"]
    images = [block for block in converted_blocks if block.get("type") == "image"]
    assert len(images) == 22
    assert all(block["source"]["type"] == "base64" for block in images)
    assert all(block["source"]["data"] for block in images)
