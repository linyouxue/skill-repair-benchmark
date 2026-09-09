"""Offline checks for organizer-verified Original-pass exclusions.

Guards implementation commit 8393b98e576a3fc5cf542c663e18cfea6bbd6701.
"""

from __future__ import annotations

import json
import shutil
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from evaluation.scripts import evaluate_skill_diagnosis_repair as evaluator


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def original_pass_case(tmp_path: Path) -> dict:
    source_root = tmp_path / "gold-originals"
    submission_root = tmp_path / "submission"
    trusted_root = tmp_path / "organizer"
    submission_root.mkdir()
    (trusted_root / "snapshots").mkdir(parents=True)
    (trusted_root / "reports").mkdir()
    tasks = []
    for task_id, defect_count in [("original-ok", 2), ("needs-repair", 1)]:
        original = source_root / task_id
        original.mkdir(parents=True)
        (original / "SKILL.md").write_text(
            f"Original instructions for {task_id}.\n", encoding="utf-8"
        )
        tasks.append(
            {
                "task_id": task_id,
                "original_bundle": str(original.resolve()),
                "defects": [
                    {
                        "defect_id": f"D{index}",
                        "description": f"Defect {index}",
                        "locations": [{"file": "SKILL.md", "section": "Rules"}],
                        "repair_requirement": f"Required behavior {index}",
                    }
                    for index in range(1, defect_count + 1)
                ],
            }
        )
    final = submission_root / "normal-final"
    final.mkdir()
    (final / "SKILL.md").write_text(
        "Required behavior 1 is now explicit.\n", encoding="utf-8"
    )
    case = {
        "gold": {"benchmark_version": "v1", "tasks": tasks},
        "submission": {
            "method_id": "method-a",
            "benchmark_version": "v1",
            "tasks": [
                {
                    "task_id": "original-ok",
                    "original_pass": True,
                    "original_run_id": "r1",
                },
                {
                    "task_id": "needs-repair",
                    "repaired_bundle": "normal-final",
                    "diagnoses": [
                        {
                            "prediction_id": "P1",
                            "description": "Defect 1",
                            "locations": [{"file": "SKILL.md", "section": "Rules"}],
                        }
                    ],
                },
            ],
        },
        "trusted": {
            "method_id": "method-a",
            "benchmark_version": "v1",
            "protocol_id": "orig-v1",
            "runs": [],
        },
        "gold_path": tmp_path / "gold.json",
        "submission_path": submission_root / "submission.json",
        "trusted_path": trusted_root / "verified.json",
        "trusted_root": trusted_root,
    }
    add_verified_run(case, "original-ok", "r1")
    save_case(case)
    return case


def add_verified_run(case: dict, task_id: str, run_id: str) -> None:
    original = next(
        row["original_bundle"]
        for row in case["gold"]["tasks"]
        if row["task_id"] == task_id
    )
    snapshot = case["trusted_root"] / "snapshots" / task_id
    shutil.copytree(original, snapshot)
    report = case["trusted_root"] / "reports" / f"{task_id}.txt"
    report.write_text("Organizer verifier: all checks passed.\n", encoding="utf-8")
    case["trusted"]["runs"].append(
        {
            "task_id": task_id,
            "run_id": run_id,
            "passed": True,
            "execution_ok": True,
            "original_bundle": f"snapshots/{task_id}",
            "verifier_report": f"reports/{task_id}.txt",
        }
    )


def save_case(case: dict) -> None:
    write_json(case["gold_path"], case["gold"])
    write_json(case["submission_path"], case["submission"])
    write_json(case["trusted_path"], case["trusted"])


def mark_all_passed(case: dict, *, explicit_empty_diagnoses: bool = False) -> None:
    case["submission"]["tasks"][1] = {
        "task_id": "needs-repair",
        "original_pass": True,
        "original_run_id": "r2",
    }
    add_verified_run(case, "needs-repair", "r2")
    if explicit_empty_diagnoses:
        for task in case["submission"]["tasks"]:
            task["diagnoses"] = []
    save_case(case)


@pytest.fixture
def fake_model(monkeypatch: pytest.MonkeyPatch) -> tuple[Mock, Mock]:
    client = Mock()
    constructor = Mock(return_value=client)
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=constructor))
    monkeypatch.setenv("ORIGINAL_PASS_TEST_KEY", "offline-mock-only")
    monkeypatch.delenv("ORIGINAL_PASS_MISSING_KEY", raising=False)
    return constructor, client


def base_args(case: dict, output: Path, *, trusted: bool = True) -> list[str]:
    args = [
        "--gold",
        str(case["gold_path"]),
        "--submission",
        str(case["submission_path"]),
        "--output",
        str(output),
    ]
    if trusted:
        args += ["--verified-original-passes", str(case["trusted_path"])]
    return args


def execute_args(case: dict, output: Path, *, trusted: bool = True) -> list[str]:
    return [
        *base_args(case, output, trusted=trusted),
        "--execute",
        "--judge-model",
        "mock-model",
        "--api-key-env",
        "ORIGINAL_PASS_TEST_KEY",
    ]


def normal_judgments() -> tuple[dict, dict]:
    diagnosis = {
        "diagnoses": [
            {
                "prediction_id": "P1",
                "matched_defect_id": "D1",
                "same_defect": True,
                "location_correct": True,
                "confidence": 0.99,
                "reason": "Same independently described defect.",
            }
        ]
    }
    repair = {
        "repairs": [
            {
                "defect_id": "D1",
                "repair_present": True,
                "repair_correct": True,
                "confidence": 0.99,
                "reason": "The final text satisfies the requirement.",
            }
        ],
        "extra_modifications": [],
        "regression": {
            "substantive_change": True,
            "detected": False,
            "new_defects": [],
            "confidence": 0.99,
            "reason": "No originally correct behavior is broken.",
        },
    }
    return diagnosis, repair


def completion(value: dict) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(content=json.dumps(value)),
            )
        ],
        usage=None,
    )


def replay_pack(case: dict) -> dict:
    diagnosis, repair = normal_judgments()
    return {
        "method_id": "method-a",
        "benchmark_version": "v1",
        "prompt_version": "skill-diagnosis-repair-v2.1",
        "judge_model": "mock-model",
        "tasks": [
            {
                "task_id": "original-ok",
                "status": "skipped_original_pass",
                "original_run": {
                    **case["trusted"]["runs"][0],
                    "protocol_id": "orig-v1",
                },
            },
            {
                "task_id": "needs-repair",
                "diagnosis_result": diagnosis,
                "repair_result": repair,
            },
        ],
    }


def test_mixed_submission_skips_verified_original_pass_and_replays_without_model(
    original_pass_case: dict,
    fake_model: tuple[Mock, Mock],
    tmp_path: Path,
) -> None:
    case = original_pass_case
    constructor, client = fake_model
    client.chat.completions.create.side_effect = [
        completion(value) for value in normal_judgments()
    ]
    output = tmp_path / "mixed-result"

    assert evaluator.main(execute_args(case, output)) == 0

    constructor.assert_called_once()
    calls = client.chat.completions.create.call_args_list
    assert len(calls) == 2
    for call in calls:
        assert (
            json.loads(call.kwargs["messages"][1]["content"])["task_id"]
            == "needs-repair"
        )
    requests = [
        json.loads(line)
        for line in (output / "requests.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(requests) == 2
    assert {row["task_id"] for row in requests} == {"needs-repair"}
    summary = read_json(output / "summary.json")
    assert summary["status"] == "complete"
    assert summary["task_count"] == 2
    assert summary["total_gold_defect_count"] == 3
    assert summary["skipped_original_pass_task_count"] == 1
    assert summary["skipped_gold_defect_count"] == 2
    assert summary["evaluated_task_count"] == summary["scored_task_count"] == 1
    assert summary["evaluated_gold_defect_count"] == 1
    assert summary["skipped_original_pass_rate"] == 0.5
    assert summary["skipped_original_pass_task_ids"] == ["original-ok"]
    for name in ("diagnosis", "repair"):
        assert summary["metrics"][name]["tp"] == 1
        assert summary["metrics"][name]["fp"] == summary["metrics"][name]["fn"] == 0
        assert summary["metrics"][name]["f1"] == 1
    skipped = read_json(output / "skipped_tasks.json")["tasks"]
    assert len(skipped) == 1
    assert skipped[0]["task_id"] == "original-ok"
    assert skipped[0]["status"] == "skipped_original_pass"
    assert skipped[0]["defect_ids"] == ["D1", "D2"]
    assert skipped[0]["gold_defect_count"] == 2
    assert skipped[0]["original_run"]["run_id"] == "r1"
    assert skipped[0]["original_run"]["protocol_id"] == "orig-v1"
    assert skipped[0]["original_run"]["verifier_report"]
    detail_rows = {
        row["task_id"]: row for row in read_json(output / "details.json")["tasks"]
    }
    assert detail_rows["original-ok"]["metrics"] is None
    saved = read_json(output / "judge_responses.json")
    assert {row["task_id"] for row in saved["tasks"]} == {"original-ok", "needs-repair"}
    saved_skip = next(row for row in saved["tasks"] if row["task_id"] == "original-ok")
    assert saved_skip["status"] == "skipped_original_pass"
    assert saved_skip["original_run"]["run_id"] == "r1"
    assert "diagnosis_result" not in saved_skip and "repair_result" not in saved_skip

    constructor.reset_mock()
    client.chat.completions.create.reset_mock()
    replay_output = tmp_path / "replayed-result"
    assert (
        evaluator.main(
            [
                *base_args(case, replay_output),
                "--judge-responses",
                str(output / "judge_responses.json"),
            ]
        )
        == 0
    )
    constructor.assert_not_called()
    client.chat.completions.create.assert_not_called()
    assert read_json(replay_output / "summary.json")["metrics"] == summary["metrics"]


@pytest.mark.parametrize(
    "empty_diagnoses", [False, True], ids=["omitted", "empty-list"]
)
def test_all_original_passes_need_no_model_or_key_and_have_no_evaluation_scores(
    original_pass_case: dict,
    fake_model: tuple[Mock, Mock],
    tmp_path: Path,
    empty_diagnoses: bool,
) -> None:
    case = original_pass_case
    mark_all_passed(case, explicit_empty_diagnoses=empty_diagnoses)
    constructor, client = fake_model
    output = tmp_path / "all-skipped"

    assert (
        evaluator.main(
            [
                *base_args(case, output),
                "--execute",
                "--api-key-env",
                "ORIGINAL_PASS_MISSING_KEY",
            ]
        )
        == 0
    )

    constructor.assert_not_called()
    client.chat.completions.create.assert_not_called()
    summary = read_json(output / "summary.json")
    assert summary["status"] == "complete"
    assert summary["metrics"] is None
    assert summary["task_count"] == summary["skipped_original_pass_task_count"] == 2
    assert (
        summary["total_gold_defect_count"] == summary["skipped_gold_defect_count"] == 3
    )
    assert summary["evaluated_task_count"] == summary["scored_task_count"] == 0
    assert summary["evaluated_gold_defect_count"] == 0
    assert summary["skipped_original_pass_rate"] == 1
    assert set(summary["skipped_original_pass_task_ids"]) == {
        "original-ok",
        "needs-repair",
    }
    assert (output / "requests.jsonl").read_text(encoding="utf-8").strip() == ""
    assert len(read_json(output / "skipped_tasks.json")["tasks"]) == 2


def test_all_original_passes_dry_run_prepares_zero_requests(
    original_pass_case: dict,
    fake_model: tuple[Mock, Mock],
    tmp_path: Path,
) -> None:
    case = original_pass_case
    mark_all_passed(case)
    constructor, _ = fake_model
    output = tmp_path / "all-skipped-dry-run"

    assert evaluator.main([*base_args(case, output), "--dry-run"]) == 0

    constructor.assert_not_called()
    summary = read_json(output / "summary.json")
    assert summary["maximum_judge_requests"] == 0
    assert summary["input_characters"] == 0
    assert summary["skipped_original_pass_task_count"] == 2
    assert (output / "requests.jsonl").read_text(encoding="utf-8").strip() == ""


@pytest.mark.parametrize(
    "invalid",
    [
        "no-organizer-proof",
        "string-bool",
        "integer-bool",
        "null-bool",
        "null-diagnoses",
        "nonempty-diagnoses",
        "hidden-repaired-bundle",
        "normal-missing-diagnoses",
        "missing-gold-task",
    ],
)
def test_invalid_submission_cannot_hide_behind_original_pass_before_api(
    original_pass_case: dict,
    fake_model: tuple[Mock, Mock],
    tmp_path: Path,
    invalid: str,
) -> None:
    case = original_pass_case
    constructor, _ = fake_model
    skipped, normal = case["submission"]["tasks"]
    if invalid == "string-bool":
        skipped["original_pass"] = "true"
    elif invalid == "integer-bool":
        skipped["original_pass"] = 1
    elif invalid == "null-bool":
        skipped["original_pass"] = None
    elif invalid == "null-diagnoses":
        skipped["diagnoses"] = None
    elif invalid == "nonempty-diagnoses":
        skipped["diagnoses"] = deepcopy(normal["diagnoses"])
    elif invalid == "hidden-repaired-bundle":
        skipped["repaired_bundle"] = "normal-final"
    elif invalid == "normal-missing-diagnoses":
        normal.pop("diagnoses")
    elif invalid == "missing-gold-task":
        case["submission"]["tasks"].pop()
    save_case(case)

    assert (
        evaluator.main(
            execute_args(
                case,
                tmp_path / "reject-submission",
                trusted=invalid != "no-organizer-proof",
            )
        )
        == 2
    )
    constructor.assert_not_called()


@pytest.mark.parametrize(
    "invalid",
    [
        "wrong-method",
        "wrong-version",
        "wrong-run-id",
        "missing-proof-task",
        "extra-proof-task",
        "duplicate-run-id",
        "false-passed",
        "fake-passed-bool",
        "execution-failed",
        "changed-snapshot",
        "missing-snapshot-file",
        "extra-snapshot-file",
        "missing-report",
        "empty-report",
    ],
)
def test_invalid_organizer_evidence_is_rejected_before_api(
    original_pass_case: dict,
    fake_model: tuple[Mock, Mock],
    tmp_path: Path,
    invalid: str,
) -> None:
    case = original_pass_case
    constructor, _ = fake_model
    manifest = case["trusted"]
    run = manifest["runs"][0]
    snapshot = case["trusted_root"] / run["original_bundle"]
    report = case["trusted_root"] / run["verifier_report"]
    if invalid == "wrong-method":
        manifest["method_id"] = "different-method"
    elif invalid == "wrong-version":
        manifest["benchmark_version"] = "different-version"
    elif invalid == "wrong-run-id":
        run["run_id"] = "wrong-run"
    elif invalid == "missing-proof-task":
        manifest["runs"] = []
    elif invalid == "extra-proof-task":
        add_verified_run(case, "needs-repair", "r2")
    elif invalid == "duplicate-run-id":
        mark_all_passed(case)
        manifest["runs"][1]["run_id"] = "r1"
        case["submission"]["tasks"][1]["original_run_id"] = "r1"
    elif invalid == "false-passed":
        run["passed"] = False
    elif invalid == "fake-passed-bool":
        run["passed"] = "true"
    elif invalid == "execution-failed":
        run["execution_ok"] = False
    elif invalid == "changed-snapshot":
        (snapshot / "SKILL.md").write_text(
            "A repaired bundle must not count as Original.\n", encoding="utf-8"
        )
    elif invalid == "missing-snapshot-file":
        (snapshot / "SKILL.md").unlink()
    elif invalid == "extra-snapshot-file":
        (snapshot / "extra.md").write_text("Unexpected file.\n", encoding="utf-8")
    elif invalid == "missing-report":
        report.unlink()
    else:
        report.write_bytes(b"")
    save_case(case)

    assert evaluator.main(execute_args(case, tmp_path / "reject-evidence")) == 2
    constructor.assert_not_called()


@pytest.mark.parametrize(
    "invalid",
    [
        "no-trusted-file",
        "wrong-run-id",
        "wrong-protocol",
        "fake-extra-skip",
        "missing-task",
        "skip-with-judgments",
    ],
)
def test_replay_cannot_create_or_change_original_pass_exclusions(
    original_pass_case: dict,
    fake_model: tuple[Mock, Mock],
    tmp_path: Path,
    invalid: str,
) -> None:
    case = original_pass_case
    constructor, client = fake_model
    pack = replay_pack(case)
    if invalid == "wrong-run-id":
        pack["tasks"][0]["original_run"]["run_id"] = "different-run"
    elif invalid == "wrong-protocol":
        pack["tasks"][0]["original_run"]["protocol_id"] = "different-protocol"
    elif invalid == "fake-extra-skip":
        pack["tasks"][1] = {
            "task_id": "needs-repair",
            "status": "skipped_original_pass",
            "original_run": {"run_id": "forged", "protocol_id": "orig-v1"},
        }
    elif invalid == "missing-task":
        pack["tasks"].pop()
    elif invalid == "skip-with-judgments":
        pack["tasks"][0]["diagnosis_result"] = {"diagnoses": []}
    responses_path = tmp_path / "forged-replay.json"
    write_json(responses_path, pack)

    assert (
        evaluator.main(
            [
                *base_args(
                    case,
                    tmp_path / "reject-replay",
                    trusted=invalid != "no-trusted-file",
                ),
                "--judge-responses",
                str(responses_path),
            ]
        )
        == 2
    )
    constructor.assert_not_called()
    client.chat.completions.create.assert_not_called()


def test_normal_judge_failure_still_blocks_mixed_submission_scores(
    original_pass_case: dict,
    fake_model: tuple[Mock, Mock],
    tmp_path: Path,
) -> None:
    case = original_pass_case
    constructor, client = fake_model
    diagnosis, repair = normal_judgments()
    repair["repairs"] = []
    client.chat.completions.create.side_effect = [
        completion(diagnosis),
        completion(repair),
    ]
    output = tmp_path / "mixed-judge-error"

    assert evaluator.main(execute_args(case, output)) == 2

    constructor.assert_called_once()
    assert client.chat.completions.create.call_count == 2
    summary = read_json(output / "summary.json")
    assert summary["status"] == "error"
    assert summary["metrics"] is None
    assert summary["skipped_original_pass_task_count"] == 1
    assert summary["evaluated_task_count"] == 1
    assert summary["scored_task_count"] == 0
