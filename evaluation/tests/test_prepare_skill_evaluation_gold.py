"""Offline acceptance tests for converting manual RI annotations into evaluation Gold.

Guards implementation commit 8393b98e576a3fc5cf542c663e18cfea6bbd6701.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from evaluation.scripts.evaluate_skill_diagnosis_repair import load_inputs
from evaluation.scripts.prepare_skill_evaluation_gold import convert_gold


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def conversion_case(tmp_path: Path) -> dict:
    map_base = tmp_path / "annotation-map"
    original = map_base / "original" / "skills"
    (original / "a").mkdir(parents=True)
    (original / "b" / "references").mkdir(parents=True)
    (original / "a" / "SKILL.md").write_text(
        "# 区间规则\n原始内容。\n", encoding="utf-8"
    )
    (original / "b" / "references" / "rules.md").write_text(
        "# 导出规则\n原始内容。\n", encoding="utf-8"
    )
    prompts_path = map_base / "original" / "prompts.json"
    prompts = ["处理视频区间并保留原音轨。", "输出字幕应使用 UTF-8 编码。"]
    write_json(prompts_path, prompts)
    output_base = tmp_path / "evaluation-output"
    output_base.mkdir()
    source = [
        {
            "id": "t",
            # Nonconsecutive, deliberately reversed IDs must retain their source identity.
            "RI-007": {
                "tag": "skill_missing_guidance",
                "skill_location": [
                    {
                        "skill_name": "a",
                        "skill_file": "skills/a/SKILL.md",
                        "skill_section": "区间规则",
                        "problematic_part": "原规则错误合并了有间隔的区间。",
                    },
                    {
                        "skill_name": "b",
                        "skill_file": "skills/b/references/rules.md",
                        "skill_section": "导出规则",
                        "problematic_part": "参考文件保留了相互矛盾的合并说明。",
                    },
                ],
                "descrip_skill_error": "  缺少一致的区间边界规则。\n两个文件的说明冲突。  ",
                "gold_repair": "只合并重叠或首尾相接的区间；同步修正参考文件。\n保留原音轨。",  # noqa: RUF001
                "validation_status": "partial",
                "validation_evidence": {"verifier_passed": 2, "verifier_total": 3},
                "verifier_issue": "验收器没有覆盖正间隔边界。",
                "annotation": "保留人工标注；不能因为尚未完整验收而删除此 RI。",  # noqa: RUF001
            },
            "RI-002": {
                "tag": "skill_ambiguous_guidance",
                "skill_location": [
                    {
                        "skill_name": "a",
                        "skill_file": "skills/a/SKILL.md",
                        "skill_section": "字幕编码",
                        "problematic_part": "使用系统默认编码。",
                    }
                ],
                "descrip_skill_error": "字幕编码说明不明确，可能产生乱码。",  # noqa: RUF001
                "gold_repair": "字幕文件统一使用 UTF-8 编码。",
                "validation_status": "not_verified",
            },
        }
    ]
    bundle_map = {
        "tasks": [
            {
                "task_id": "t",
                "original_bundle": "original/skills",
                "task_prompts": "original/prompts.json",
                "notes": ["原始未修复 bundle 的来源备注。"],
            }
        ]
    }
    return {
        "source": source,
        "bundle_map": bundle_map,
        "map_base": map_base,
        "output_base": output_base,
        "original": original,
        "prompts_path": prompts_path,
        "prompts": prompts,
    }


def convert_case(case: dict) -> dict:
    return convert_gold(
        case["source"],
        case["bundle_map"],
        map_base=case["map_base"],
        output_base=case["output_base"],
        benchmark_version="manual-gold-v1",
    )


def test_conversion_preserves_manual_fields_and_one_defect_per_source_ri(
    conversion_case: dict,
) -> None:
    case = conversion_case
    original_source = deepcopy(case["source"])
    original_map = deepcopy(case["bundle_map"])

    converted = convert_case(case)

    assert converted["benchmark_version"] == "manual-gold-v1"
    assert len(converted["tasks"]) == 1
    task = converted["tasks"][0]
    assert task["task_id"] == "t"
    assert len(task["defects"]) == 2
    assert not Path(task["original_bundle"]).is_absolute()
    assert (case["output_base"] / task["original_bundle"]).resolve() == case[
        "original"
    ].resolve()
    for prompt in case["prompts"]:
        assert prompt in task["task_context"]

    defects = {row["source_repair_id"]: row for row in task["defects"]}
    assert set(defects) == {"RI-007", "RI-002"}
    for rid, defect in defects.items():
        source = original_source[0][rid]
        assert defect["defect_id"] == "D" + rid.removeprefix("RI-")
        assert defect["description"] == source["descrip_skill_error"]
        assert defect["repair_requirement"] == source["gold_repair"]
        assert defect["root_cause"] == source["tag"]
        assert defect["source_details"]["skill_location"] == source["skill_location"]
        for key in (
            "validation_status",
            "validation_evidence",
            "verifier_issue",
            "annotation",
        ):
            if key in source:
                assert defect["source_details"][key] == source[key]
    assert defects["RI-007"]["locations"] == [
        {"file": "a/SKILL.md", "section": "区间规则"},
        {"file": "b/references/rules.md", "section": "导出规则"},
    ]
    assert defects["RI-002"]["source_details"]["validation_status"] == "not_verified"
    assert case["source"] == original_source
    assert case["bundle_map"] == original_map


def test_defect_ids_do_not_depend_on_source_key_order(conversion_case: dict) -> None:
    case = conversion_case
    first = convert_case(case)
    task = case["source"][0]
    case["source"] = [{"id": "t", "RI-002": task["RI-002"], "RI-007": task["RI-007"]}]

    second = convert_case(case)

    first_ids = {
        row["source_repair_id"]: row["defect_id"]
        for row in first["tasks"][0]["defects"]
    }
    second_ids = {
        row["source_repair_id"]: row["defect_id"]
        for row in second["tasks"][0]["defects"]
    }
    assert first_ids == second_ids == {"RI-002": "D002", "RI-007": "D007"}


def test_location_removes_only_one_leading_skills_component(
    conversion_case: dict,
) -> None:
    case = conversion_case
    nested = case["original"] / "skills" / "a"
    nested.mkdir(parents=True)
    (nested / "SKILL.md").write_text("Nested skill directory.\n", encoding="utf-8")
    case["source"][0]["RI-002"]["skill_location"][0]["skill_file"] = (
        "skills/skills/a/SKILL.md"
    )

    converted = convert_case(case)

    defect = next(
        row
        for row in converted["tasks"][0]["defects"]
        if row["source_repair_id"] == "RI-002"
    )
    assert defect["locations"][0]["file"] == "skills/a/SKILL.md"


@pytest.mark.parametrize(
    "invalid",
    [
        "unknown-tag",
        "missing-description",
        "missing-repair",
        "empty-locations",
        "missing-location-file",
        "missing-original-bundle",
        "missing-map-task",
        "empty-prompts",
        "nonstring-prompts",
    ],
)
def test_invalid_source_or_missing_original_evidence_is_rejected(
    conversion_case: dict, invalid: str
) -> None:
    case = conversion_case
    ri = case["source"][0]["RI-007"]
    mapping = case["bundle_map"]["tasks"][0]
    if invalid == "unknown-tag":
        ri["tag"] = "model_execution_error"
    elif invalid == "missing-description":
        ri.pop("descrip_skill_error")
    elif invalid == "missing-repair":
        ri.pop("gold_repair")
    elif invalid == "empty-locations":
        ri["skill_location"] = []
    elif invalid == "missing-location-file":
        ri["skill_location"][0]["skill_file"] = "skills/absent/SKILL.md"
    elif invalid == "missing-original-bundle":
        mapping["original_bundle"] = "missing-original"
    elif invalid == "missing-map-task":
        mapping["task_id"] = "different-task"
    elif invalid == "empty-prompts":
        write_json(case["prompts_path"], [])
    else:
        write_json(case["prompts_path"], ["Valid instruction", 123])

    with pytest.raises(ValueError):
        convert_case(case)


def test_converted_gold_loads_with_the_evaluator_and_empty_diagnoses(
    conversion_case: dict,
) -> None:
    case = conversion_case
    converted = convert_case(case)
    gold_path = case["output_base"] / "gold.json"
    write_json(gold_path, converted)
    submission_base = case["output_base"] / "submission"
    submission_base.mkdir()
    repaired = submission_base / "skills" / "a"
    repaired.mkdir(parents=True)
    (repaired / "SKILL.md").write_text("Submitted final skill.\n", encoding="utf-8")
    submission_path = submission_base / "submission.json"
    write_json(
        submission_path,
        {
            "method_id": "offline-method",
            "benchmark_version": "manual-gold-v1",
            "tasks": [{"task_id": "t", "diagnoses": [], "repaired_bundle": "skills"}],
        },
    )

    loaded_gold, _, gold_tasks, submissions = load_inputs(gold_path, submission_path)

    assert loaded_gold == converted
    assert set(gold_tasks) == set(submissions) == {"t"}
    assert len(gold_tasks["t"]["defects"]) == 2
    assert submissions["t"]["diagnoses"] == []
