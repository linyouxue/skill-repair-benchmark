"""Offline acceptance tests for the defect-level diagnosis/repair score contract.

Guards implementation commit 8393b98e576a3fc5cf542c663e18cfea6bbd6701.
"""

from __future__ import annotations

import json
import os
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest

from evaluation.scripts.evaluate_skill_diagnosis_repair import (
    aggregate_results,
    build_requests,
    evaluate_task,
    precision_recall_f1,
)


def make_case() -> tuple[dict, dict, dict]:
    """Three gold defects, two correct diagnoses, and one successful repair."""
    gold = {
        "task_id": "t",
        "defects": [
            {
                "defect_id": f"D{index}",
                "description": f"Independent defect {index}",
                "locations": [{"file": "a.md", "section": f"section-{index}"}],
                "repair_requirement": f"Required behavior for defect {index}",
            }
            for index in range(1, 4)
        ],
    }
    submission = {
        "task_id": "t",
        "diagnoses": [
            {
                "prediction_id": f"P{index}",
                "description": f"Predicted defect {index}",
                "locations": [{"file": "a.md", "section": f"section-{index}"}],
            }
            for index in range(1, 4)
        ],
    }
    judgment = {
        "diagnoses": [
            {
                "prediction_id": "P1",
                "matched_defect_id": "D1",
                "same_defect": True,
                "location_correct": True,
                "confidence": 0.99,
                "reason": "Same faulty behavior and matching section.",
            },
            {
                "prediction_id": "P2",
                "matched_defect_id": "D2",
                "same_defect": True,
                "location_correct": False,
                "confidence": 0.99,
                "reason": "Correct faulty behavior, but wrong section.",
            },
            {
                "prediction_id": "P3",
                "matched_defect_id": None,
                "same_defect": False,
                "location_correct": False,
                "confidence": 0.99,
                "reason": "The reported restriction is not a defect.",
            },
        ],
        "repairs": [
            {
                "defect_id": "D1",
                "repair_present": True,
                "repair_correct": True,
                "confidence": 0.99,
                "reason": "Final content meets the required behavior.",
            },
            {
                "defect_id": "D2",
                "repair_present": True,
                "repair_correct": False,
                "confidence": 0.99,
                "reason": "An attempted change leaves the defect unresolved.",
            },
            {
                "defect_id": "D3",
                "repair_present": False,
                "repair_correct": False,
                "confidence": 0.99,
                "reason": "No change addresses this defect.",
            },
        ],
        "extra_modifications": [
            {
                "item_id": "E1",
                "classification": "harmful_or_unsupported",
                "confidence": 0.99,
                "reason": "The new instruction removes required audio.",
            },
            {
                "item_id": "E2",
                "classification": "benign",
                "confidence": 0.99,
                "reason": "Only a heading is renamed.",
            },
            {
                "item_id": "E3",
                "classification": "possible_new_defect",
                "confidence": 0.99,
                "reason": "This appears to fix an original issue absent from gold.",
            },
        ],
        "regression": {
            "substantive_change": True,
            "detected": True,
            "new_defects": [
                {
                    "defect_id": "R1",
                    "description": "Required audio is removed.",
                    "evidence": "The final file says to discard the original audio.",
                }
            ],
            "confidence": 0.99,
            "reason": "Audio was preserved by the original instructions.",
        },
    }
    return gold, submission, judgment


def assert_counts(metrics: dict, tp: int, fp: int, fn: int) -> None:
    assert (metrics["tp"], metrics["fp"], metrics["fn"]) == (tp, fp, fn)


def test_scores_defects_and_extra_modifications_without_counting_benign_edits() -> None:
    gold, submission, judgment = make_case()

    result = evaluate_task(gold, submission, judgment)

    assert result["task_id"] == "t"
    assert result["status"] == "complete"
    metrics = result["metrics"]
    assert_counts(metrics["diagnosis"], tp=2, fp=1, fn=1)
    assert metrics["diagnosis"]["precision"] == pytest.approx(2 / 3)
    assert metrics["diagnosis"]["recall"] == pytest.approx(2 / 3)
    assert metrics["diagnosis"]["f1"] == pytest.approx(2 / 3)
    assert_counts(metrics["repair"], tp=1, fp=2, fn=2)
    assert metrics["repair"]["precision"] == pytest.approx(1 / 3)
    assert metrics["repair"]["recall"] == pytest.approx(1 / 3)
    assert metrics["repair"]["f1"] == pytest.approx(1 / 3)
    assert metrics["location_accuracy"] == pytest.approx(1 / 2)
    assert metrics["regression"] is True
    assert metrics["regression_count"] == 1
    assert metrics["substantive_change"] is True
    assert metrics["possible_new_defect_count"] == 1
    # A possible gold omission is recorded without blocking this frozen-gold score.
    assert result["review_items"]


def test_repair_success_does_not_require_a_correct_diagnosis() -> None:
    gold, submission, judgment = make_case()
    judgment["diagnoses"][0].update(
        matched_defect_id=None, same_defect=False, location_correct=False
    )

    metrics = evaluate_task(gold, submission, judgment)["metrics"]

    assert_counts(metrics["diagnosis"], tp=1, fp=2, fn=2)
    assert_counts(metrics["repair"], tp=1, fp=2, fn=2)


def test_missing_prediction_location_cannot_receive_location_credit() -> None:
    gold, submission, judgment = make_case()
    submission["diagnoses"][0].pop("locations")

    metrics = evaluate_task(gold, submission, judgment)["metrics"]

    assert_counts(metrics["diagnosis"], tp=2, fp=1, fn=1)
    assert metrics["location_accuracy"] == 0


@pytest.mark.parametrize("missing", [False, True], ids=["null", "missing"])
def test_diagnosis_output_is_required_and_cannot_be_null(missing: bool) -> None:
    gold, submission, judgment = make_case()
    if missing:
        submission.pop("diagnoses")
    else:
        submission["diagnoses"] = None
    judgment["diagnoses"] = []

    with pytest.raises(ValueError):
        evaluate_task(gold, submission, judgment)


def test_empty_diagnosis_predictions_count_every_gold_defect_as_missed() -> None:
    gold, submission, judgment = make_case()
    submission["diagnoses"] = []
    judgment["diagnoses"] = []

    metrics = evaluate_task(gold, submission, judgment)["metrics"]

    assert_counts(metrics["diagnosis"], tp=0, fp=0, fn=3)
    assert metrics["diagnosis"]["precision"] is None
    assert metrics["diagnosis"]["recall"] == 0
    assert metrics["diagnosis"]["f1"] == 0
    assert metrics["location_accuracy"] is None
    assert_counts(metrics["repair"], tp=1, fp=2, fn=2)


def test_two_predictions_claiming_one_gold_require_review_instead_of_first_wins() -> (
    None
):
    gold, submission, judgment = make_case()
    judgment["diagnoses"][1]["matched_defect_id"] = "D1"

    for diagnoses in [judgment["diagnoses"], list(reversed(judgment["diagnoses"]))]:
        judgment["diagnoses"] = diagnoses
        result = evaluate_task(gold, submission, judgment)
        assert result["status"] == "needs_review"
        assert result["metrics"] is None
        assert result["review_items"]


@pytest.mark.parametrize(
    "section", ["diagnoses", "repairs", "extra_modifications", "regression"]
)
def test_low_confidence_warns_without_changing_scores(section: str) -> None:
    gold, submission, judgment = make_case()
    expected_metrics = evaluate_task(gold, submission, judgment)["metrics"]
    row = judgment[section] if section == "regression" else judgment[section][0]
    row["confidence"] = 0.79

    result = evaluate_task(gold, submission, judgment, confidence_threshold=0.8)

    assert result["status"] == "complete"
    assert result["metrics"] == expected_metrics
    warnings = [
        item for item in result["review_items"] if item["kind"] == "low_confidence"
    ]
    assert len(warnings) == 1
    assert warnings[0]["blocking"] is False
    assert result["confidence_summary"] == {
        "low_confidence_count": 1,
        "total_judgment_count": 10,
        "low_confidence_rate": 0.1,
    }


def test_confidence_at_threshold_is_accepted() -> None:
    gold, submission, judgment = make_case()
    judgment["repairs"][0]["confidence"] = 0.8

    result = evaluate_task(gold, submission, judgment, confidence_threshold=0.8)

    assert result["status"] == "complete"
    assert not any(item["kind"] == "low_confidence" for item in result["review_items"])
    assert result["confidence_summary"] == {
        "low_confidence_count": 0,
        "total_judgment_count": 10,
        "low_confidence_rate": 0.0,
    }


def test_all_low_confidence_judgments_still_produce_the_same_scores() -> None:
    gold, submission, judgment = make_case()
    expected_metrics = evaluate_task(gold, submission, judgment)["metrics"]
    rows = (
        judgment["diagnoses"]
        + judgment["repairs"]
        + judgment["extra_modifications"]
        + [judgment["regression"]]
    )
    for row in rows:
        row["confidence"] = 0.2

    result = evaluate_task(gold, submission, judgment)

    assert result["status"] == "complete"
    assert result["metrics"] == expected_metrics
    warnings = [
        item for item in result["review_items"] if item["kind"] == "low_confidence"
    ]
    assert len(warnings) == len(rows)
    assert all(item["blocking"] is False for item in warnings)
    assert result["confidence_summary"] == {
        "low_confidence_count": 10,
        "total_judgment_count": 10,
        "low_confidence_rate": 1.0,
    }


def test_low_confidence_warning_does_not_disable_real_matching_conflict_block() -> None:
    gold, submission, judgment = make_case()
    judgment["diagnoses"][1]["matched_defect_id"] = "D1"
    judgment["diagnoses"][1]["confidence"] = 0.2

    result = evaluate_task(gold, submission, judgment)

    assert result["status"] == "needs_review"
    assert result["metrics"] is None
    warnings = [
        item for item in result["review_items"] if item["kind"] == "low_confidence"
    ]
    conflicts = [
        item for item in result["review_items"] if item["kind"] == "matching_conflict"
    ]
    assert len(warnings) == 1
    assert warnings[0]["blocking"] is False
    assert len(conflicts) == 1
    assert conflicts[0]["blocking"] is True
    assert result["confidence_summary"] == {
        "low_confidence_count": 1,
        "total_judgment_count": 10,
        "low_confidence_rate": 0.1,
    }


def test_confidence_denominator_counts_regression_bundle_once_for_multiple_new_defects() -> (
    None
):
    gold, submission, judgment = make_case()
    judgment["regression"]["confidence"] = 0.5
    judgment["regression"]["new_defects"].append(
        {
            "defect_id": "R2",
            "description": "Required metadata is removed.",
            "evidence": "The final rule also drops required metadata.",
        }
    )

    result = evaluate_task(gold, submission, judgment)

    assert result["status"] == "complete"
    assert result["metrics"]["regression_count"] == 2
    assert result["confidence_summary"] == {
        "low_confidence_count": 1,
        "total_judgment_count": 10,
        "low_confidence_rate": 0.1,
    }


@pytest.mark.parametrize("section", ["diagnoses", "repairs"])
def test_missing_judge_rows_are_invalid_not_implicit_misses(section: str) -> None:
    gold, submission, judgment = make_case()
    judgment[section].pop()

    with pytest.raises(ValueError):
        evaluate_task(gold, submission, judgment)


@pytest.mark.parametrize(
    ("section", "field"),
    [
        ("diagnoses", "prediction_id"),
        ("diagnoses", "matched_defect_id"),
        ("repairs", "defect_id"),
    ],
)
def test_judge_cannot_reference_unknown_source_ids(section: str, field: str) -> None:
    gold, submission, judgment = make_case()
    judgment[section][0][field] = "UNKNOWN"

    with pytest.raises(ValueError):
        evaluate_task(gold, submission, judgment)


@pytest.mark.parametrize(
    "source", ["gold", "submission", "diagnoses", "repairs", "extras", "regressions"]
)
def test_duplicate_ids_are_rejected_before_scoring(source: str) -> None:
    gold, submission, judgment = make_case()
    rows = {
        "gold": gold["defects"],
        "submission": submission["diagnoses"],
        "diagnoses": judgment["diagnoses"],
        "repairs": judgment["repairs"],
        "extras": judgment["extra_modifications"],
        "regressions": judgment["regression"]["new_defects"],
    }[source]
    rows.append(deepcopy(rows[0]))

    with pytest.raises(ValueError):
        evaluate_task(gold, submission, judgment)


@pytest.mark.parametrize(
    "source", ["gold", "submission", "diagnoses", "repairs", "extras", "regressions"]
)
def test_missing_ids_are_rejected_before_scoring(source: str) -> None:
    gold, submission, judgment = make_case()
    row, field = {
        "gold": (gold["defects"][0], "defect_id"),
        "submission": (submission["diagnoses"][0], "prediction_id"),
        "diagnoses": (judgment["diagnoses"][0], "prediction_id"),
        "repairs": (judgment["repairs"][0], "defect_id"),
        "extras": (judgment["extra_modifications"][0], "item_id"),
        "regressions": (judgment["regression"]["new_defects"][0], "defect_id"),
    }[source]
    row.pop(field)

    with pytest.raises(ValueError):
        evaluate_task(gold, submission, judgment)


@pytest.mark.parametrize("bad_bool", ["false", 0, 1, None])
def test_repair_boolean_fields_must_not_use_python_truthiness(bad_bool) -> None:
    gold, submission, judgment = make_case()
    judgment["repairs"][0]["repair_correct"] = bad_bool

    with pytest.raises(ValueError):
        evaluate_task(gold, submission, judgment)


@pytest.mark.parametrize(
    "bad_confidence", ["0.99", True, -0.1, 1.1, float("nan"), float("inf")]
)
def test_invalid_confidence_is_rejected_not_treated_as_low_confidence(
    bad_confidence,
) -> None:
    gold, submission, judgment = make_case()
    judgment["repairs"][0]["confidence"] = bad_confidence

    with pytest.raises(ValueError):
        evaluate_task(gold, submission, judgment)


def test_correct_repair_requires_a_repair_to_be_present() -> None:
    gold, submission, judgment = make_case()
    judgment["repairs"][0]["repair_present"] = False

    with pytest.raises(ValueError):
        evaluate_task(gold, submission, judgment)


@pytest.mark.parametrize(
    "inconsistency",
    ["hidden-new-defect", "missing-new-defect", "no-substantive-change"],
)
def test_regression_flags_must_agree_with_the_new_defect_evidence(
    inconsistency: str,
) -> None:
    gold, submission, judgment = make_case()
    regression = judgment["regression"]
    if inconsistency == "hidden-new-defect":
        regression["detected"] = False
    elif inconsistency == "missing-new-defect":
        regression["new_defects"] = []
    else:
        regression["substantive_change"] = False

    with pytest.raises(ValueError):
        evaluate_task(gold, submission, judgment)


def test_unchanged_bundle_cannot_get_repair_or_regression_credit_from_judge_claims() -> (
    None
):
    gold, submission, judgment = make_case()

    result = evaluate_task(gold, submission, judgment, has_changes=False)

    assert result["status"] == "needs_review"
    assert result["metrics"] is None
    assert result["review_items"]


def test_unchanged_bundle_with_no_repair_attempts_has_only_repair_false_negatives() -> (
    None
):
    gold, submission, judgment = make_case()
    for repair in judgment["repairs"]:
        repair.update(repair_present=False, repair_correct=False)
    judgment["extra_modifications"] = []
    judgment["regression"].update(
        substantive_change=False, detected=False, new_defects=[]
    )

    result = evaluate_task(gold, submission, judgment, has_changes=False)

    assert result["status"] == "complete"
    metrics = result["metrics"]
    assert_counts(metrics["repair"], tp=0, fp=0, fn=3)
    assert metrics["repair"]["precision"] is None
    assert metrics["repair"]["recall"] == 0
    assert metrics["repair"]["f1"] == 0
    assert metrics["regression"] is False
    assert metrics["regression_count"] == 0
    assert metrics["substantive_change"] is False


@pytest.mark.parametrize(
    ("tp", "fp", "fn", "precision", "recall", "f1"),
    [
        (0, 0, 0, None, None, None),
        (0, 0, 3, None, 0.0, 0.0),
        (0, 2, 0, 0.0, None, 0.0),
        (0, 2, 3, 0.0, 0.0, 0.0),
        (2, 1, 3, 2 / 3, 2 / 5, 1 / 2),
    ],
)
def test_metric_zero_denominators_and_f1_use_explicit_count_formula(
    tp: int, fp: int, fn: int, precision, recall, f1
) -> None:
    metrics = precision_recall_f1(tp, fp, fn)

    assert_counts(metrics, tp, fp, fn)
    for field, expected in [("precision", precision), ("recall", recall), ("f1", f1)]:
        if expected is None:
            assert metrics[field] is None
        else:
            assert metrics[field] == pytest.approx(expected)


def make_single_success_case() -> tuple[dict, dict, dict]:
    gold, submission, judgment = make_case()
    gold["task_id"] = submission["task_id"] = "single-success"
    gold["defects"] = gold["defects"][:1]
    submission["diagnoses"] = submission["diagnoses"][:1]
    judgment["diagnoses"] = judgment["diagnoses"][:1]
    judgment["repairs"] = judgment["repairs"][:1]
    judgment["extra_modifications"] = []
    judgment["regression"].update(detected=False, new_defects=[])
    return gold, submission, judgment


def make_no_repair_case() -> tuple[dict, dict, dict]:
    gold, submission, judgment = make_case()
    gold["task_id"] = submission["task_id"] = "no-repair"
    for repair in judgment["repairs"]:
        repair.update(repair_present=False, repair_correct=False)
    judgment["extra_modifications"] = []
    judgment["regression"].update(
        substantive_change=False, detected=False, new_defects=[]
    )
    return gold, submission, judgment


def test_aggregate_uses_micro_counts_instead_of_averaging_task_percentages() -> None:
    first = evaluate_task(*make_case())
    second = evaluate_task(*make_single_success_case())

    metrics = aggregate_results([first, second])

    assert_counts(metrics["diagnosis"], tp=3, fp=1, fn=1)
    assert metrics["diagnosis"]["precision"] == pytest.approx(3 / 4)
    assert metrics["diagnosis"]["recall"] == pytest.approx(3 / 4)
    assert metrics["diagnosis"]["f1"] == pytest.approx(3 / 4)
    assert_counts(metrics["repair"], tp=2, fp=2, fn=2)
    assert metrics["repair"]["precision"] == pytest.approx(1 / 2)
    assert metrics["repair"]["recall"] == pytest.approx(1 / 2)
    assert metrics["repair"]["f1"] == pytest.approx(1 / 2)
    assert metrics["location_correct_count"] == 2
    assert metrics["location_accuracy"] == pytest.approx(2 / 3)
    assert metrics["diagnosis_task_count"] == 2
    assert metrics["failed_gold_repair_count"] == 1
    assert metrics["harmful_extra_repair_count"] == 1
    assert metrics["possible_new_defect_count"] == 1


def test_aggregate_regression_counts_bundles_with_substantive_changes_only() -> None:
    gold, submission, judgment = make_case()
    judgment["regression"]["new_defects"].append(
        {
            "defect_id": "R2",
            "description": "Required metadata is removed.",
            "evidence": "The final file now instructs removal of required metadata.",
        }
    )
    regressed = evaluate_task(gold, submission, judgment)
    successful = evaluate_task(*make_single_success_case())
    unchanged = evaluate_task(*make_no_repair_case(), has_changes=False)

    metrics = aggregate_results([regressed, successful, unchanged])

    assert metrics["substantively_modified_bundles"] == 2
    assert metrics["regressed_bundles"] == 1
    assert metrics["regression_rate"] == pytest.approx(1 / 2)
    # Two new defects in one bundle count once in the rate, twice in the defect count.
    assert metrics["regression_count"] == 2


def test_aggregate_regression_rate_is_null_when_all_changes_are_absent_or_cosmetic() -> (
    None
):
    unchanged = evaluate_task(*make_no_repair_case(), has_changes=False)
    gold, submission, judgment = make_no_repair_case()
    gold["task_id"] = submission["task_id"] = "cosmetic-only"
    judgment["extra_modifications"] = [
        {
            "item_id": "E1",
            "classification": "benign",
            "confidence": 0.99,
            "reason": "Only a section title was rephrased without changing behavior.",
        }
    ]
    cosmetic = evaluate_task(gold, submission, judgment, has_changes=True)

    metrics = aggregate_results([unchanged, cosmetic])

    assert metrics["substantively_modified_bundles"] == 0
    assert metrics["regressed_bundles"] == 0
    assert metrics["regression_rate"] is None
    assert metrics["regression_count"] == 0
    assert_counts(metrics["repair"], tp=0, fp=0, fn=6)


def test_aggregate_withholds_overall_score_if_any_task_needs_review() -> None:
    complete = evaluate_task(*make_single_success_case())
    gold, submission, judgment = make_case()
    judgment["diagnoses"][1]["matched_defect_id"] = "D1"
    pending = evaluate_task(gold, submission, judgment)

    assert pending["status"] == "needs_review"
    assert aggregate_results([complete, pending]) is None
    assert aggregate_results([pending, complete]) is None


@pytest.mark.parametrize("metric_name", ["diagnosis", "repair"])
def test_aggregate_rejects_null_metrics_instead_of_excluding_tasks(
    metric_name: str,
) -> None:
    complete = evaluate_task(*make_case())
    invalid = evaluate_task(*make_single_success_case())
    invalid["metrics"][metric_name] = None

    with pytest.raises(ValueError):
        aggregate_results([complete, invalid])


def make_bundle_case(tmp_path: Path) -> tuple[dict, dict, Path, Path]:
    gold, submission, _ = make_case()
    gold_base = tmp_path / "trusted-gold"
    original = gold_base / "original"
    original.mkdir(parents=True)
    (original / "a.md").write_text("ORIGINAL_SNAPSHOT_TOKEN\n", encoding="utf-8")
    submission_base = tmp_path / "submission"
    repaired = submission_base / "tasks" / "t" / "skills"
    repaired.mkdir(parents=True)
    (repaired / "a.md").write_text("FINAL_SNAPSHOT_TOKEN\n", encoding="utf-8")
    gold["original_bundle"] = str(original.resolve())
    gold["task_context"] = (
        "Preserve the original audio while correcting interval merging."
    )
    submission["repaired_bundle"] = "tasks/t/skills"
    return gold, submission, gold_base, submission_base


def get_request_payload(request: dict) -> dict:
    messages = [message for message in request["messages"] if message["role"] == "user"]
    assert len(messages) == 1
    return json.loads(messages[0]["content"])


def test_build_requests_separates_diagnosis_and_repair_evidence(tmp_path: Path) -> None:
    gold, submission, gold_base, submission_base = make_bundle_case(tmp_path)
    gold["defects"][0]["repair_requirement"] = "REPAIR_REQUIREMENT_TOKEN"
    submission["diagnoses"][0]["description"] = "PREDICTION_ONLY_TOKEN"

    requests, changed, binary_changes = build_requests(
        gold, submission, gold_base, submission_base, 100_000
    )

    assert set(requests) == {"diagnosis", "repair"}
    assert changed is True
    assert binary_changes == []
    for phase, request in requests.items():
        assert request["phase"] == phase
        assert request["task_id"] == "t"
        assert any(message["role"] == "system" for message in request["messages"])

    diagnosis = get_request_payload(requests["diagnosis"])
    repair = get_request_payload(requests["repair"])
    diagnosis_text = json.dumps(diagnosis)
    repair_text = json.dumps(repair)
    assert "predictions" in diagnosis
    assert "PREDICTION_ONLY_TOKEN" in diagnosis_text
    assert "ORIGINAL_SNAPSHOT_TOKEN" in diagnosis_text
    assert "FINAL_SNAPSHOT_TOKEN" not in diagnosis_text
    assert "REPAIR_REQUIREMENT_TOKEN" not in diagnosis_text
    assert "final_files" not in diagnosis
    assert "diff" not in diagnosis
    assert "repair_requirement" not in diagnosis_text
    assert "predictions" not in repair
    assert "PREDICTION_ONLY_TOKEN" not in repair_text
    assert "ORIGINAL_SNAPSHOT_TOKEN" in repair_text
    assert "FINAL_SNAPSHOT_TOKEN" in repair_text
    assert "REPAIR_REQUIREMENT_TOKEN" in repair_text
    assert repair["diff"]


def test_build_requests_whitelists_gold_predictions_and_nested_locations(
    tmp_path: Path,
) -> None:
    gold, submission, gold_base, submission_base = make_bundle_case(tmp_path)
    gold["internal_notes"] = "TASK_EXTRA_SECRET_TOKEN"
    submission["self_reported_result"] = "SUBMISSION_EXTRA_SECRET_TOKEN"
    for defect in gold["defects"]:
        defect["reference_repair"] = "GOLD_EXTRA_SECRET_TOKEN"
        defect["annotation_history"] = {"text": "GOLD_HISTORY_SECRET_TOKEN"}
        defect["locations"][0]["debug_note"] = "LOCATION_EXTRA_SECRET_TOKEN"
    for prediction in submission["diagnoses"]:
        prediction["repair_suggestion"] = "PREDICTION_EXTRA_SECRET_TOKEN"
        prediction["final_files"] = [{"text": "FINAL_EXTRA_SECRET_TOKEN"}]
        prediction["locations"][0]["private_note"] = "PREDICTION_LOCATION_SECRET_TOKEN"

    requests, _, _ = build_requests(
        gold, submission, gold_base, submission_base, 100_000
    )

    serialized = json.dumps(requests)
    assert "SECRET_TOKEN" not in serialized
    diagnosis = get_request_payload(requests["diagnosis"])
    repair = get_request_payload(requests["repair"])
    for defect in diagnosis["gold_defects"]:
        assert set(defect) == {"defect_id", "description", "locations"}
    for defect in repair["gold_defects"]:
        assert set(defect) == {
            "defect_id",
            "description",
            "locations",
            "repair_requirement",
        }
    for prediction in diagnosis["predictions"]:
        assert set(prediction) == {"prediction_id", "description", "locations"}
    for row in (
        diagnosis["gold_defects"] + diagnosis["predictions"] + repair["gold_defects"]
    ):
        for location in row["locations"]:
            assert set(location) <= {"file", "section", "start_line", "end_line"}


@pytest.mark.parametrize("missing", [False, True], ids=["null", "missing"])
def test_build_requests_rejects_unprovided_diagnoses(
    tmp_path: Path, missing: bool
) -> None:
    gold, submission, gold_base, submission_base = make_bundle_case(tmp_path)
    if missing:
        submission.pop("diagnoses")
    else:
        submission["diagnoses"] = None

    with pytest.raises(ValueError):
        build_requests(gold, submission, gold_base, submission_base, 100_000)


def forbid_external_reads(monkeypatch: pytest.MonkeyPatch, external: Path) -> None:
    original_read_bytes = Path.read_bytes
    external = external.resolve()

    def guarded_read_bytes(path: Path) -> bytes:
        if path.resolve().is_relative_to(external):
            pytest.fail(f"Untrusted external path was read before rejection: {path}")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)


@pytest.mark.parametrize(
    "invalid_path",
    [
        "../external",
        "..\\external",
        "tasks/t/skills/../../../../external",
        "/outside",
        "C:\\outside",
        "C:/outside",
        "C:outside",
        "//server/share/outside",
        "\\\\server\\share\\outside",
        "\\outside",
        "absolute-internal",
        "absolute-external",
    ],
)
def test_repaired_bundle_must_be_a_contained_relative_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, invalid_path: str
) -> None:
    gold, submission, gold_base, submission_base = make_bundle_case(tmp_path)
    external = tmp_path / "external"
    external.mkdir()
    (external / "secret.md").write_text("DO_NOT_READ_EXTERNAL_TOKEN", encoding="utf-8")
    if invalid_path == "absolute-internal":
        invalid_path = str((submission_base / submission["repaired_bundle"]).resolve())
    elif invalid_path == "absolute-external":
        invalid_path = str(external.resolve())
    submission["repaired_bundle"] = invalid_path
    forbid_external_reads(monkeypatch, external)

    with pytest.raises(ValueError):
        build_requests(gold, submission, gold_base, submission_base, 100_000)


@pytest.mark.parametrize(
    "link_kind", ["bundle-root", "nested-directory", "nested-file"]
)
def test_repaired_bundle_rejects_external_symlinks_before_reading_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, link_kind: str
) -> None:
    gold, submission, gold_base, submission_base = make_bundle_case(tmp_path)
    external = tmp_path / "external"
    external.mkdir()
    secret = external / "secret.md"
    secret.write_text("DO_NOT_READ_EXTERNAL_TOKEN", encoding="utf-8")
    repaired = submission_base / submission["repaired_bundle"]
    if link_kind == "bundle-root":
        link = submission_base / "linked-bundle"
        submission["repaired_bundle"] = "linked-bundle"
    else:
        link = repaired / "external-link"
    target = secret if link_kind == "nested-file" else external
    try:
        link.symlink_to(target, target_is_directory=link_kind != "nested-file")
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"This host cannot create test symlinks: {exc}")
    forbid_external_reads(monkeypatch, external)

    with pytest.raises(ValueError):
        build_requests(gold, submission, gold_base, submission_base, 100_000)


@pytest.mark.skipif(os.name != "nt", reason="Windows junctions are platform-specific")
@pytest.mark.parametrize("link_kind", ["bundle-root", "nested-directory"])
def test_repaired_bundle_rejects_external_windows_junctions_before_reading_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, link_kind: str
) -> None:
    gold, submission, gold_base, submission_base = make_bundle_case(tmp_path)
    external = tmp_path / "external"
    external.mkdir()
    (external / "secret.md").write_text("DO_NOT_READ_EXTERNAL_TOKEN", encoding="utf-8")
    if link_kind == "bundle-root":
        link = submission_base / "junction-bundle"
        submission["repaired_bundle"] = "junction-bundle"
    else:
        link = submission_base / submission["repaired_bundle"] / "junction-directory"
    quoted_link = "'" + str(link).replace("'", "''") + "'"
    quoted_target = "'" + str(external).replace("'", "''") + "'"
    command = (
        f"New-Item -ItemType Junction -Path {quoted_link} -Target {quoted_target} "
        "-ErrorAction Stop | Out-Null"
    )
    try:
        creation = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        pytest.skip(f"PowerShell is unavailable for creating a test junction: {exc}")
    if creation.returncode:
        pytest.skip(
            f"This host cannot create test junctions: {creation.stderr.strip()}"
        )
    try:
        forbid_external_reads(monkeypatch, external)
        with pytest.raises(ValueError):
            build_requests(gold, submission, gold_base, submission_base, 100_000)
    finally:
        # Remove only the junction itself; the external target must remain intact.
        link.rmdir()
    assert (external / "secret.md").is_file()
