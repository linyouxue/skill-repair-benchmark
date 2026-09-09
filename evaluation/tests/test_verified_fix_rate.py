"""Guards Verified Fix Rate reporting from commit 11ae9ae05a9a5238eb627caf79bae89499cad4a0."""

from __future__ import annotations

import csv
import json
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from evaluation.scripts import evaluate_skill_diagnosis_repair as evaluator

# Known vector for _bundle_digest in src/benchflow/benchmark_executor.py:
# length-prefixed UTF-8 path and body records, ordered by relative path.
FINAL_FILES = {
    "SKILL.md": b"Final skill.\n",
    "references/rules.txt": b"Keep original audio.\n",
}
FINAL_SHA256 = "sha256:9b3c1d581ccad7bb66c4c2f4cb5c15a9bbec2164e9b796befe9f0210ce40df41"


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def verifier_case(tmp_path: Path) -> dict:
    submission_base = tmp_path / "submission"
    original = tmp_path / "original"
    original.mkdir()
    (original / "SKILL.md").write_text("Original faulty rule.\n", encoding="utf-8")
    gold_tasks, submitted_tasks = {}, {}
    for tid in ("passed", "failed", "invalid", "missing", "original-pass"):
        final = submission_base / tid
        for name, body in FINAL_FILES.items():
            target = final / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
        gold_tasks[tid] = {
            "task_id": tid,
            "original_bundle": str(original),
            "defects": [
                {
                    "defect_id": "D1",
                    "description": "Faulty rule",
                    "repair_requirement": "Final skill.",
                    "locations": [{"file": "SKILL.md"}],
                }
            ],
        }
        submitted_tasks[tid] = {"task_id": tid, "diagnoses": [], "repaired_bundle": tid}
    reports, requests = {}, {}
    for tid in ("passed", "failed", "invalid"):
        # These fields follow BenchmarkResult.to_dict, not Unix executor imports.
        reports[tid] = {
            "task_id": tid,
            "rollout_id": f"{tid}-r1",
            "method_id": "method-a",
            "stage": "final",
            "protocol_id": "skillrepair-v1",
            "protocol_version": 2,
            "model": "openai/gpt-5.5",
            "provider_route": "openrouter",
            "provider_base_url": "https://openrouter.ai/api/v1",
            "provider_protocol": "openai",
            "reasoning_effort": "medium",
            "task_passed": tid == "passed",
            "execution_ok": True,
            "reward": 1.0 if tid == "passed" else 0.0,
            "agent_iterations": 2,
            "provider_requests": 2,
            "wall_time_sec": 1.0,
            "cost_usd": 0.0,
            "termination_reason": "EXECUTOR_VERIFIER_PRIVATE_TOKEN",
            "error": None,
            "error_category": None,
            "verifier_error": None,
            "verifier_error_category": None,
            "export_error": None,
            "protocol_evidence_valid": True,
            "trajectory_complete": True,
            "iteration_accounting_complete": True,
            "skill_exposure_verified": True,
            "rollout_dir": str(tmp_path / "runs" / tid),
            "result_json": str(tmp_path / "runs" / tid / "result.json"),
        }
        requests[tid] = {
            "schema_version": 1,
            "protocol": {
                "protocol_id": "skillrepair-v1",
                "protocol_version": 2,
            },
            "model_selection": {
                "model": "openai/gpt-5.5",
                "provider_route": "openrouter",
                "reasoning_effort": "medium",
            },
            "task_id": tid,
            "task_digest": "fixture-task-digest",
            "condition": "method-skill",
            "method_id": "method-a",
            "stage": "final",
            "rollout_id": f"{tid}-r1",
            "skill_bundle": str(submission_base / tid),
            "skill_bundle_manifest": {
                "skill_bundle_sha256": FINAL_SHA256,
                "preloaded_skill_count": 1,
                "preloaded_skill_files": ["SKILL.md"],
                "skill_bundle_file_count": 2,
                "skill_bundle_bytes": sum(map(len, FINAL_FILES.values())),
            },
            "verifier_proxy": {},
        }
    reports["invalid"].update(
        execution_ok=False,
        task_passed=None,
        reward=None,
        error="Provider failed",
    )
    case = {
        "gold_tasks": gold_tasks,
        "submitted_tasks": submitted_tasks,
        "submission": {
            "method_id": "method-a",
            "benchmark_version": "v1",
            "tasks": list(submitted_tasks.values()),
        },
        "skipped": {
            "original-pass": {
                "task_id": "original-pass",
                "status": "skipped_original_pass",
            }
        },
        "submission_base": submission_base,
        "reports": reports,
        "requests": requests,
        "registry_path": tmp_path / "executor-results.json",
        "registry": {
            "method_id": "method-a",
            "benchmark_version": "v1",
            "tasks": [
                {
                    "task_id": tid,
                    "benchmark_result": f"runs/{tid}/benchmark_result.json",
                }
                for tid in reports
            ],
        },
    }
    persist(case)
    return case


def persist(case: dict) -> None:
    write_json(case["registry_path"], case["registry"])
    for tid, report in case["reports"].items():
        directory = case["registry_path"].parent / "runs" / tid
        write_json(directory / "benchmark_result.json", report)
        write_json(directory / "executor_request.json", case["requests"][tid])


def summarize(case: dict, *, supplied: bool = True) -> dict:
    return evaluator.verified_fix_report(
        case["registry_path"] if supplied else None,
        case["submission"],
        case["gold_tasks"],
        case["submitted_tasks"],
        case["skipped"],
        case["submission_base"],
        100_000,
    )


def test_mixed_results_count_only_valid_final_runs_and_expose_coverage(
    verifier_case: dict,
) -> None:
    result = summarize(verifier_case)

    assert result["verified_fix_rate"] == 0.5
    assert result["verified_fix_status"] == "partial"
    assert result["verified_fix_eligible_task_count"] == 4
    assert result["verified_fix_valid_task_count"] == 2
    assert result["verified_fix_passed_task_count"] == 1
    assert result["verified_fix_failed_task_count"] == 1
    assert result["verified_fix_invalid_task_count"] == 1
    assert result["verified_fix_missing_task_count"] == 1
    assert result["verified_fix_coverage"] == 0.5
    assert {row["task_id"]: row["status"] for row in result["tasks"]} == {
        "passed": "passed",
        "failed": "failed",
        "invalid": "invalid_execution",
        "missing": "missing_result",
        "original-pass": "skipped_original_pass",
    }


@pytest.mark.parametrize("evidence_complete", [True, False])
def test_incomplete_pass_and_missing_verdict_form_a_complete_scored_batch(
    verifier_case: dict, evidence_complete: bool
) -> None:
    """Guards the verdict-policy correction to the evaluator in commit 5889a8f."""
    case = verifier_case
    case["gold_tasks"] = {
        tid: case["gold_tasks"][tid] for tid in ("passed", "failed", "original-pass")
    }
    case["registry"]["tasks"] = case["registry"]["tasks"][:2]
    case["reports"]["passed"]["trajectory_complete"] = False
    case["reports"]["failed"].update(
        task_passed=None,
        reward=None,
        protocol_evidence_valid=evidence_complete,
        trajectory_complete=False,
        iteration_accounting_complete=evidence_complete,
        skill_exposure_verified=evidence_complete,
    )
    persist(case)

    result = summarize(case)

    assert result["verified_fix_rate"] == 0.5
    assert result["verified_fix_coverage"] == 1.0
    assert result["verified_fix_status"] == "complete"
    assert result["verified_fix_valid_task_count"] == 2
    assert result["verified_fix_passed_task_count"] == 1
    assert result["verified_fix_failed_task_count"] == 1
    assert result["verified_fix_invalid_task_count"] == 0
    assert result["verified_fix_missing_task_count"] == 0
    rows = {row["task_id"]: row for row in result["tasks"]}
    assert rows["passed"]["status"] == "passed"
    assert rows["failed"]["status"] == "failed"
    assert rows["failed"]["task_passed"] is None
    assert rows["failed"]["reward"] is None
    assert case["reports"]["failed"]["execution_ok"] is True


@pytest.mark.parametrize("mode", ["not-provided", "empty-results", "all-skipped"])
def test_unavailable_verified_fix_rate_is_null_not_zero(
    verifier_case: dict, mode: str
) -> None:
    case = verifier_case
    case["registry"]["tasks"] = []
    if mode == "all-skipped":
        case["skipped"] = {tid: {"task_id": tid} for tid in case["gold_tasks"]}
    persist(case)

    result = summarize(case, supplied=mode != "not-provided")

    assert result["verified_fix_rate"] is None
    assert result["verified_fix_valid_task_count"] == 0
    assert result["verified_fix_passed_task_count"] == 0
    assert (
        result["verified_fix_status"]
        == {
            "not-provided": "not_provided",
            "empty-results": "partial",
            "all-skipped": "no_eligible_tasks",
        }[mode]
    )
    if mode == "all-skipped":
        assert result["verified_fix_eligible_task_count"] == 0
        assert result["verified_fix_coverage"] is None
    else:
        assert result["verified_fix_missing_task_count"] == 4
        assert result["verified_fix_coverage"] == 0.0


@pytest.mark.parametrize(
    "updates",
    [
        {
            "execution_ok": False,
            "task_passed": None,
            "reward": None,
            "error": "crashed",
        },
        {
            "execution_ok": False,
            "task_passed": None,
            "reward": None,
            "verifier_error": "verifier crashed",
        },
    ],
)
def test_unusable_but_well_formed_execution_is_excluded(
    verifier_case: dict, updates: dict
) -> None:
    case = verifier_case
    case["reports"]["passed"].update(updates)
    persist(case)

    result = summarize(case)

    assert result["verified_fix_invalid_task_count"] == 2
    assert result["verified_fix_valid_task_count"] == 1
    assert result["verified_fix_rate"] == 0.0


@pytest.mark.parametrize(
    "updates",
    [
        {"execution_ok": "true"},
        {"task_passed": 1},
        {"reward": True},
        {"reward": float("nan")},
        {"task_passed": False, "reward": 1.0},
        {"task_passed": None},
        {"protocol_evidence_valid": False},
        {"iteration_accounting_complete": False},
        {"skill_exposure_verified": False},
        {"verifier_error": "verifier failed"},
        {"export_error": "export failed"},
    ],
)
def test_invalid_types_or_contradictory_successful_result_are_input_errors(
    verifier_case: dict, updates: dict
) -> None:
    case = verifier_case
    case["reports"]["passed"].update(updates)
    persist(case)

    with pytest.raises(ValueError):
        summarize(case)


@pytest.mark.parametrize(
    "invalid",
    [
        "manifest-method",
        "manifest-version",
        "unknown-task",
        "duplicate-task",
        "skipped-task",
        "report-task",
        "request-method",
        "rollout-id",
        "condition",
        "request-model",
        "request-effort",
        "request-protocol",
        "request-protocol-version",
        "report-protocol-version",
        "bundle-hash",
        "changed-final-reference",
        "missing-report",
        "missing-request",
        "malformed-json",
    ],
)
def test_executor_identity_must_bind_to_this_submission_and_final_bundle(
    verifier_case: dict, invalid: str
) -> None:
    case = verifier_case
    report, request = case["reports"]["passed"], case["requests"]["passed"]
    if invalid in ("manifest-method", "manifest-version"):
        case["registry"][
            "method_id" if invalid == "manifest-method" else "benchmark_version"
        ] = "wrong"
    elif invalid in ("unknown-task", "skipped-task"):
        case["registry"]["tasks"].append(
            {
                "task_id": "unknown" if invalid == "unknown-task" else "original-pass",
                "benchmark_result": "unused.json",
            }
        )
    elif invalid == "duplicate-task":
        case["registry"]["tasks"].append(deepcopy(case["registry"]["tasks"][0]))
    elif invalid == "report-task":
        report["task_id"] = "failed"
    elif invalid == "request-method":
        request["method_id"] = "different-method"
    elif invalid == "rollout-id":
        request["rollout_id"] = "other-round"
    elif invalid == "condition":
        request["condition"] = "original-skill"
    elif invalid in ("request-model", "request-effort"):
        request["model_selection"][
            "model" if invalid == "request-model" else "reasoning_effort"
        ] = "different"
    elif invalid == "request-protocol":
        request["protocol"]["protocol_id"] = "different"
    elif invalid == "request-protocol-version":
        request["protocol"]["protocol_version"] = 1
    elif invalid == "report-protocol-version":
        report["protocol_version"] = 1
    elif invalid == "bundle-hash":
        request["skill_bundle_manifest"]["skill_bundle_sha256"] = "sha256:" + "0" * 64
    elif invalid == "changed-final-reference":
        (case["submission_base"] / "passed" / "references" / "rules.txt").write_text(
            "A different repair round.\n", encoding="utf-8"
        )
    persist(case)
    report_path = (
        case["registry_path"].parent / "runs" / "passed" / "benchmark_result.json"
    )
    if invalid == "missing-report":
        report_path.unlink()
    elif invalid == "missing-request":
        report_path.with_name("executor_request.json").unlink()
    elif invalid == "malformed-json":
        report_path.write_text("{", encoding="utf-8")

    with pytest.raises((ValueError, OSError)):
        summarize(case)


def test_guard_metadata_is_not_an_evaluation_gate(verifier_case: dict) -> None:
    case = verifier_case
    case["requests"]["passed"]["completion_guard"] = {
        "enabled": False,
        "text_only_retry_limit_per_step": 0,
    }
    case["reports"]["passed"]["completion_guard"] = "different-or-legacy"
    persist(case)

    result = summarize(case)

    assert result["verified_fix_passed_task_count"] == 1
    assert result["verified_fix_valid_task_count"] == 2


@pytest.mark.parametrize("field", ["model", "reasoning_effort", "protocol_id"])
def test_individually_consistent_runs_cannot_mix_executor_settings(
    verifier_case: dict, field: str
) -> None:
    case = verifier_case
    case["reports"]["failed"][field] = "different-setting"
    target = case["requests"]["failed"][
        "protocol" if field == "protocol_id" else "model_selection"
    ]
    target[field] = "different-setting"
    persist(case)

    with pytest.raises(ValueError):
        summarize(case)


def prepare_cli_case(case: dict) -> tuple[Path, Path, Path]:
    gold_path = case["registry_path"].parent / "gold.json"
    submission_path = case["submission_base"] / "submission.json"
    judge_path = case["registry_path"].parent / "judge-responses.json"
    write_json(
        gold_path, {"benchmark_version": "v1", "tasks": [case["gold_tasks"]["passed"]]}
    )
    write_json(
        submission_path,
        {**case["submission"], "tasks": [case["submitted_tasks"]["passed"]]},
    )
    write_json(
        judge_path,
        {
            "method_id": "method-a",
            "benchmark_version": "v1",
            "prompt_version": "skill-diagnosis-repair-v2.1",
            "judge_model": "offline-example",
            "tasks": [
                {
                    "task_id": "passed",
                    "diagnosis_result": {"diagnoses": []},
                    "repair_result": {
                        "repairs": [
                            {
                                "defect_id": "D1",
                                "repair_present": True,
                                "repair_correct": True,
                                "confidence": 0.99,
                                "reason": "Final requirement satisfied.",
                            }
                        ],
                        "extra_modifications": [],
                        "regression": {
                            "substantive_change": True,
                            "detected": False,
                            "new_defects": [],
                            "confidence": 0.99,
                            "reason": "Original behavior retained.",
                        },
                    },
                }
            ],
        },
    )
    case["registry"]["tasks"] = case["registry"]["tasks"][:1]
    persist(case)
    return gold_path, submission_path, judge_path


@pytest.mark.parametrize(
    ("updates", "expected_rate", "expected_status"),
    [
        ({}, 1.0, "passed"),
        ({"trajectory_complete": False}, 1.0, "passed"),
        ({"task_passed": None, "reward": None}, 0.0, "failed"),
    ],
    ids=["complete-pass", "incomplete-trajectory-pass", "missing-verdict-failure"],
)
def test_cli_offline_reporting_keeps_f1_separate_and_verifier_out_of_judge_payload(
    verifier_case: dict,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    updates: dict,
    expected_rate: float,
    expected_status: str,
) -> None:
    """Guards the verdict-policy correction to the evaluator in commit 5889a8f."""
    case = verifier_case
    constructor = Mock()
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=constructor))
    gold, submission, judgments = prepare_cli_case(case)
    case["reports"]["passed"].update(updates)
    persist(case)
    common = [
        "--gold",
        str(gold),
        "--submission",
        str(submission),
        "--judge-responses",
        str(judgments),
    ]
    baseline, enriched = tmp_path / "baseline", tmp_path / "enriched"

    assert evaluator.main([*common, "--output", str(baseline)]) == 0
    assert (
        evaluator.main(
            [
                *common,
                "--output",
                str(enriched),
                "--executor-results",
                str(case["registry_path"]),
            ]
        )
        == 0
    )

    before, after = (
        read_json(baseline / "summary.json"),
        read_json(enriched / "summary.json"),
    )
    assert before["verified_fix_rate"] is None
    assert before["verified_fix_status"] == "not_provided"
    assert after["metrics"] == before["metrics"]
    assert after["metrics"]["diagnosis"]["f1"] == 0.0
    assert after["metrics"]["repair"]["f1"] == 1.0
    assert after["verified_fix_rate"] == expected_rate
    assert after["verified_fix_coverage"] == 1.0
    assert after["verified_fix_status"] == "complete"
    assert after["verified_fix_valid_task_count"] == 1
    assert after["verified_fix_passed_task_count"] == int(expected_rate)
    assert after["verified_fix_failed_task_count"] == 1 - int(expected_rate)
    verifier_results = read_json(enriched / "verifier_results.json")
    for key, value in after.items():
        if key.startswith("verified_fix_"):
            assert verifier_results[key] == value
    assert verifier_results["tasks"][0]["status"] == expected_status
    if expected_status == "failed":
        assert verifier_results["tasks"][0]["task_passed"] is None
        assert verifier_results["tasks"][0]["reward"] is None
    with (enriched / "summary.csv").open(encoding="utf-8-sig", newline="") as stream:
        row = next(csv.DictReader(stream))
    assert float(row["verified_fix_rate"]) == expected_rate
    assert row["verified_fix_status"] == "complete"
    assert int(row["verified_fix_valid_task_count"]) == 1
    requests = (enriched / "requests.jsonl").read_text(encoding="utf-8")
    assert "EXECUTOR_VERIFIER_PRIVATE_TOKEN" not in requests
    for line in requests.splitlines():
        payload = json.loads(json.loads(line)["messages"][1]["content"])
        assert "verified_fix_rate" not in payload and "benchmark_result" not in payload
    constructor.assert_not_called()


def test_cli_rejects_a_different_repair_round_before_model_initialization(
    verifier_case: dict,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = verifier_case
    constructor = Mock()
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=constructor))
    monkeypatch.setenv("VERIFIED_FIX_TEST_KEY", "offline-mock-only")
    gold, submission, _ = prepare_cli_case(case)
    case["requests"]["passed"]["skill_bundle_manifest"]["skill_bundle_sha256"] = (
        "sha256:" + "0" * 64
    )
    persist(case)

    assert (
        evaluator.main(
            [
                "--gold",
                str(gold),
                "--submission",
                str(submission),
                "--output",
                str(tmp_path / "reject"),
                "--executor-results",
                str(case["registry_path"]),
                "--execute",
                "--judge-model",
                "mock-model",
                "--api-key-env",
                "VERIFIED_FIX_TEST_KEY",
            ]
        )
        == 2
    )
    constructor.assert_not_called()
