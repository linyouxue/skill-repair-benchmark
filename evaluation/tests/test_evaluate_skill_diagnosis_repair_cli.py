"""Offline CLI checks for required diagnoses, submission boundaries and split judges.

Guards implementation commit 8393b98e576a3fc5cf542c663e18cfea6bbd6701.
"""

from __future__ import annotations

import csv
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from evaluation.scripts import evaluate_skill_diagnosis_repair as evaluator

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def cli_case(tmp_path: Path) -> dict:
    submission_dir = tmp_path / "submission"
    submission_dir.mkdir()
    shutil.copytree(EXAMPLES / "repaired" / "skills", submission_dir / "skills")
    gold = read_json(EXAMPLES / "gold.json")
    gold["tasks"][0]["original_bundle"] = str(
        (EXAMPLES / "original" / "skills").resolve()
    )
    submission = read_json(EXAMPLES / "submission.json")
    submission["tasks"][0]["repaired_bundle"] = "skills"
    gold_path = tmp_path / "gold.json"
    submission_path = submission_dir / "submission.json"
    write_json(gold_path, gold)
    write_json(submission_path, submission)
    return {
        "gold": gold,
        "submission": submission,
        "gold_path": gold_path,
        "submission_path": submission_path,
        "responses": read_json(EXAMPLES / "judge_responses.json"),
    }


@pytest.fixture
def fake_openai(monkeypatch: pytest.MonkeyPatch) -> tuple[Mock, Mock]:
    client = Mock()
    constructor = Mock(return_value=client)
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=constructor))
    monkeypatch.setenv("EVALUATION_TEST_API_KEY", "offline-mock-only")
    return constructor, client


def base_args(case: dict, output: Path) -> list[str]:
    return [
        "--gold",
        str(case["gold_path"]),
        "--submission",
        str(case["submission_path"]),
        "--output",
        str(output),
    ]


def execute_args(case: dict, output: Path) -> list[str]:
    return [
        *base_args(case, output),
        "--execute",
        "--judge-model",
        "offline-mock-model",
        "--api-key-env",
        "EVALUATION_TEST_API_KEY",
        "--temperature",
        "0.2",
    ]


def completion(result: dict) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(content=json.dumps(result, ensure_ascii=False)),
            )
        ],
        usage=None,
    )


def test_execute_splits_judge_inputs_and_saved_responses_replay_offline(
    cli_case: dict,
    fake_openai: tuple[Mock, Mock],
    tmp_path: Path,
) -> None:
    constructor, client = fake_openai
    expected_task = cli_case["responses"]["tasks"][0]
    client.chat.completions.create.side_effect = [
        completion(expected_task["diagnosis_result"]),
        completion(expected_task["repair_result"]),
    ]
    live_output = tmp_path / "mock-execute"

    assert evaluator.main(execute_args(cli_case, live_output)) == 0
    constructor.assert_called_once()
    calls = client.chat.completions.create.call_args_list
    assert len(calls) == 2
    diagnosis_messages, repair_messages = [call.kwargs["messages"] for call in calls]
    assert diagnosis_messages is not repair_messages
    for call in calls:
        assert [message["role"] for message in call.kwargs["messages"]] == [
            "system",
            "user",
        ]
        assert call.kwargs["model"] == "offline-mock-model"
        assert call.kwargs["temperature"] == 0.2
        assert "reasoning_effort" not in call.kwargs

    diagnosis_payload = json.loads(diagnosis_messages[1]["content"])
    repair_payload = json.loads(repair_messages[1]["content"])
    assert "final_files" not in diagnosis_payload
    assert "diff" not in diagnosis_payload
    assert "repair_requirement" not in diagnosis_messages[1]["content"]
    assert (
        "为减小文件体积，导出 MP4 视频时删除音轨。"  # noqa: RUF001
        not in diagnosis_messages[1]["content"]
    )
    assert (
        diagnosis_payload["predictions"]
        == cli_case["submission"]["tasks"][0]["diagnoses"]
    )
    assert all(
        "repair_requirement" not in defect
        for defect in diagnosis_payload["gold_defects"]
    )
    assert "predictions" not in repair_payload
    assert "prediction_id" not in repair_messages[1]["content"]
    assert repair_payload["gold_defects"] == cli_case["gold"]["tasks"][0]["defects"]
    assert repair_payload["original_files"]
    assert repair_payload["final_files"]
    assert repair_payload["diff"]

    saved_pack = read_json(live_output / "judge_responses.json")
    assert saved_pack["prompt_version"] == "skill-diagnosis-repair-v2.1"
    assert saved_pack["temperature"] == 0.2
    assert saved_pack["reasoning_effort"] is None
    saved_task = saved_pack["tasks"][0]
    assert saved_task["diagnosis_result"] == expected_task["diagnosis_result"]
    assert saved_task["repair_result"] == expected_task["repair_result"]
    assert "result" not in saved_task
    requests = [
        json.loads(line)
        for line in (live_output / "requests.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [request["phase"] for request in requests] == ["diagnosis", "repair"]

    live_summary = read_json(live_output / "summary.json")
    assert live_summary["status"] == "complete"
    assert live_summary["metrics"]["diagnosis"]["f1"] == pytest.approx(2 / 3)
    assert live_summary["metrics"]["repair"]["f1"] == pytest.approx(1 / 3)

    constructor.reset_mock()
    client.chat.completions.create.reset_mock()
    replay_output = tmp_path / "offline-replay"
    assert (
        evaluator.main(
            [
                *base_args(cli_case, replay_output),
                "--judge-responses",
                str(live_output / "judge_responses.json"),
            ]
        )
        == 0
    )
    constructor.assert_not_called()
    client.chat.completions.create.assert_not_called()
    assert (
        read_json(replay_output / "summary.json")["metrics"] == live_summary["metrics"]
    )


@pytest.mark.parametrize(
    ("flags", "expected_temperature", "expected_reasoning"),
    [
        (["--omit-temperature"], None, None),
        (["--reasoning-effort", "medium"], 0.2, "medium"),
        (["--omit-temperature", "--reasoning-effort", "medium"], None, "medium"),
    ],
    ids=["omit-temperature", "explicit-reasoning", "omit-temperature-and-reasoning"],
)
def test_execute_applies_optional_model_parameters_and_records_effective_values(
    cli_case: dict,
    fake_openai: tuple[Mock, Mock],
    tmp_path: Path,
    flags: list[str],
    expected_temperature: float | None,
    expected_reasoning: str | None,
) -> None:
    constructor, client = fake_openai
    expected_task = cli_case["responses"]["tasks"][0]
    client.chat.completions.create.side_effect = [
        completion(expected_task["diagnosis_result"]),
        completion(expected_task["repair_result"]),
    ]
    output = tmp_path / "optional-model-parameters"

    assert evaluator.main(execute_args(cli_case, output) + flags) == 0

    constructor.assert_called_once()
    calls = client.chat.completions.create.call_args_list
    assert len(calls) == 2
    for call in calls:
        if expected_temperature is None:
            assert "temperature" not in call.kwargs
        else:
            assert call.kwargs["temperature"] == expected_temperature
        if expected_reasoning is None:
            assert "reasoning_effort" not in call.kwargs
        else:
            assert call.kwargs["reasoning_effort"] == expected_reasoning
    for artifact in ("summary.json", "judge_responses.json"):
        metadata = read_json(output / artifact)
        assert metadata["temperature"] == expected_temperature
        assert metadata["reasoning_effort"] == expected_reasoning
    requests = [
        json.loads(line)
        for line in (output / "requests.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(requests) == 2
    for request in requests:
        assert request["temperature"] == expected_temperature
        assert request["reasoning_effort"] == expected_reasoning

    constructor.reset_mock()
    client.chat.completions.create.reset_mock()
    replay_output = tmp_path / "replayed-model-parameters"
    assert (
        evaluator.main(
            [
                *base_args(cli_case, replay_output),
                "--judge-responses",
                str(output / "judge_responses.json"),
            ]
        )
        == 0
    )
    replay_summary = read_json(replay_output / "summary.json")
    assert replay_summary["temperature"] == expected_temperature
    assert replay_summary["reasoning_effort"] == expected_reasoning
    constructor.assert_not_called()
    client.chat.completions.create.assert_not_called()


@pytest.mark.parametrize(
    "version",
    [None, "skill-diagnosis-repair-v1", "skill-diagnosis-repair-v2"],
    ids=["missing", "v1", "v2"],
)
def test_old_prompt_judge_pack_cannot_produce_v2_1_scores(
    cli_case: dict,
    fake_openai: tuple[Mock, Mock],
    tmp_path: Path,
    version: str | None,
) -> None:
    constructor, _ = fake_openai
    pack = cli_case["responses"]
    if version != "skill-diagnosis-repair-v2":
        task = pack["tasks"][0]
        task["result"] = {**task.pop("diagnosis_result"), **task.pop("repair_result")}
    if version is None:
        pack.pop("prompt_version")
    else:
        pack["prompt_version"] = version
    responses_path = tmp_path / "old-judgments.json"
    write_json(responses_path, pack)

    assert (
        evaluator.main(
            [
                *base_args(cli_case, tmp_path / "reject-old"),
                "--judge-responses",
                str(responses_path),
            ]
        )
        == 2
    )
    constructor.assert_not_called()


@pytest.mark.parametrize("missing", [False, True], ids=["null", "missing"])
def test_invalid_diagnoses_rejected_before_client_initialization(
    cli_case: dict,
    fake_openai: tuple[Mock, Mock],
    tmp_path: Path,
    missing: bool,
) -> None:
    constructor, _ = fake_openai
    task = cli_case["submission"]["tasks"][0]
    if missing:
        task.pop("diagnoses")
    else:
        task["diagnoses"] = None
    write_json(cli_case["submission_path"], cli_case["submission"])

    assert evaluator.main(execute_args(cli_case, tmp_path / "reject-diagnoses")) == 2
    constructor.assert_not_called()


@pytest.mark.parametrize("absolute", [False, True], ids=["relative-escape", "absolute"])
def test_external_repaired_bundle_rejected_before_client_initialization(
    cli_case: dict,
    fake_openai: tuple[Mock, Mock],
    tmp_path: Path,
    absolute: bool,
) -> None:
    constructor, _ = fake_openai
    external_bundle = tmp_path / "outside-submission"
    shutil.copytree(EXAMPLES / "repaired" / "skills", external_bundle)
    task = cli_case["submission"]["tasks"][0]
    task["repaired_bundle"] = (
        str(external_bundle.resolve()) if absolute else "../outside-submission"
    )
    write_json(cli_case["submission_path"], cli_case["submission"])

    assert evaluator.main(execute_args(cli_case, tmp_path / "reject-path")) == 2
    constructor.assert_not_called()


def test_offline_low_confidence_keeps_scores_and_exports_warning_statistics(
    cli_case: dict,
    fake_openai: tuple[Mock, Mock],
    tmp_path: Path,
) -> None:
    constructor, client = fake_openai
    responses_path = tmp_path / "responses.json"
    write_json(responses_path, cli_case["responses"])
    baseline_output = tmp_path / "baseline-confidence"
    assert (
        evaluator.main(
            [
                *base_args(cli_case, baseline_output),
                "--judge-responses",
                str(responses_path),
            ]
        )
        == 0
    )
    baseline = read_json(baseline_output / "summary.json")

    task = cli_case["responses"]["tasks"][0]
    task["diagnosis_result"]["diagnoses"][0]["confidence"] = 0.79
    task["repair_result"]["repairs"][0]["confidence"] = 0.2
    task["repair_result"]["extra_modifications"][0]["confidence"] = 0.1
    task["repair_result"]["regression"]["confidence"] = 0.0
    write_json(responses_path, cli_case["responses"])
    output = tmp_path / "low-confidence"

    assert (
        evaluator.main(
            [*base_args(cli_case, output), "--judge-responses", str(responses_path)]
        )
        == 0
    )

    summary = read_json(output / "summary.json")
    assert summary["status"] == "complete"
    assert summary["metrics"] == baseline["metrics"]
    assert summary["confidence_policy"] == "warn_only"
    assert summary["low_confidence_count"] == 4
    assert summary["total_judgment_count"] == 9
    assert summary["low_confidence_rate"] == pytest.approx(4 / 9)
    assert summary["confidence_task_count"] == 1
    assert summary["blocking_review_count"] == 0
    assert summary["review_item_count"] == 4
    details = read_json(output / "details.json")["tasks"][0]
    assert details["confidence_summary"] == {
        "low_confidence_count": 4,
        "total_judgment_count": 9,
        "low_confidence_rate": 4 / 9,
    }
    warnings = read_json(output / "review_queue.json")
    assert len(warnings) == 4
    assert all(
        item["kind"] == "low_confidence" and item["blocking"] is False
        for item in warnings
    )
    with (output / "summary.csv").open(encoding="utf-8-sig", newline="") as stream:
        csv_rows = list(csv.DictReader(stream))
    assert len(csv_rows) == 1
    csv_summary = csv_rows[0]
    assert csv_summary["status"] == "complete"
    assert int(csv_summary["low_confidence_count"]) == 4
    assert int(csv_summary["total_judgment_count"]) == 9
    assert float(csv_summary["low_confidence_rate"]) == pytest.approx(4 / 9)
    assert int(csv_summary["confidence_task_count"]) == 1
    assert float(csv_summary["diagnosis_f1"]) == pytest.approx(
        baseline["metrics"]["diagnosis"]["f1"]
    )
    assert float(csv_summary["repair_f1"]) == pytest.approx(
        baseline["metrics"]["repair"]["f1"]
    )
    constructor.assert_not_called()
    client.chat.completions.create.assert_not_called()


@pytest.mark.parametrize(
    "include_complete", [False, True], ids=["no-valid-statistics", "one-valid-task"]
)
def test_confidence_summary_excludes_tasks_without_valid_judgment_statistics(
    cli_case: dict,
    tmp_path: Path,
    include_complete: bool,
) -> None:
    results = [
        {"task_id": "bad-json", "status": "error", "metrics": None, "review_items": []},
        {
            "task_id": "changed-binary",
            "status": "needs_review",
            "metrics": None,
            "review_items": [],
        },
    ]
    if include_complete:
        task = cli_case["responses"]["tasks"][0]
        task["repair_result"]["regression"]["confidence"] = 0.5
        judgment = evaluator.combine_judgments(
            task["diagnosis_result"], task["repair_result"]
        )
        results.append(
            evaluator.evaluate_task(
                cli_case["gold"]["tasks"][0],
                cli_case["submission"]["tasks"][0],
                judgment,
            )
        )
    evaluator.write_reports(
        tmp_path,
        {
            "method_id": "test-method",
            "benchmark_version": "v1",
            "confidence_policy": "warn_only",
        },
        results,
    )

    summary = read_json(tmp_path / "summary.json")

    assert summary["metrics"] is None
    assert summary["confidence_task_count"] == int(include_complete)
    assert summary["low_confidence_count"] == int(include_complete)
    assert summary["total_judgment_count"] == (9 if include_complete else 0)
    if include_complete:
        assert summary["low_confidence_rate"] == pytest.approx(1 / 9)
    else:
        assert summary["low_confidence_rate"] is None
        with (tmp_path / "summary.csv").open(
            encoding="utf-8-sig", newline=""
        ) as stream:
            row = next(csv.DictReader(stream))
        assert row["low_confidence_rate"] == ""
        assert row["total_judgment_count"] == "0"


@pytest.mark.parametrize(
    "invalid_confidence", ["missing", None, "0.5"], ids=["missing", "null", "string"]
)
def test_invalid_confidence_remains_an_input_error_and_has_no_confidence_statistics(
    cli_case: dict,
    fake_openai: tuple[Mock, Mock],
    tmp_path: Path,
    invalid_confidence,
) -> None:
    constructor, _ = fake_openai
    row = cli_case["responses"]["tasks"][0]["repair_result"]["repairs"][0]
    if invalid_confidence == "missing":
        row.pop("confidence")
    else:
        row["confidence"] = invalid_confidence
    responses_path = tmp_path / "bad-confidence.json"
    write_json(responses_path, cli_case["responses"])
    output = tmp_path / "invalid-confidence"

    assert (
        evaluator.main(
            [*base_args(cli_case, output), "--judge-responses", str(responses_path)]
        )
        == 2
    )

    summary = read_json(output / "summary.json")
    assert summary["status"] == "error"
    assert summary["metrics"] is None
    assert summary["confidence_task_count"] == 0
    assert summary["low_confidence_count"] == 0
    assert summary["total_judgment_count"] == 0
    assert summary["low_confidence_rate"] is None
    constructor.assert_not_called()


def test_malformed_judge_json_remains_an_input_error(
    cli_case: dict,
    fake_openai: tuple[Mock, Mock],
    tmp_path: Path,
) -> None:
    constructor, _ = fake_openai
    responses_path = tmp_path / "malformed.json"
    responses_path.write_text('{"tasks": [', encoding="utf-8")

    assert (
        evaluator.main(
            [
                *base_args(cli_case, tmp_path / "malformed-result"),
                "--judge-responses",
                str(responses_path),
            ]
        )
        == 2
    )
    constructor.assert_not_called()
