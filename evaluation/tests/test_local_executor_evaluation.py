"""Guards the local evidence workflow extending the reporting base from commit e00cea8."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from evaluation.scripts import evaluate_skill_diagnosis_repair as evaluator

# Fixed executor bundle-digest vectors; no runtime executor import is required.
FINAL_FILES = {
    "SKILL.md": b"Final skill.\n",
    "references/rules.txt": b"Keep original audio.\n",
}
FINAL_SHA = "sha256:9b3c1d581ccad7bb66c4c2f4cb5c15a9bbec2164e9b796befe9f0210ce40df41"
ORIGINAL_SHA = "sha256:8e2c25207c5c149de2e501f32c2ef472285eeafd5886015e9ee5b8ac76d86b4a"


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def forbid_model_calls(monkeypatch: pytest.MonkeyPatch):
    constructor = Mock(
        side_effect=AssertionError(
            "No model client may be initialized in these offline checks"
        )
    )
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=constructor))
    monkeypatch.setenv("LOCAL_EVALUATION_TEST_KEY", "offline-mock-only")
    yield
    constructor.assert_not_called()


@pytest.fixture
def local_case(tmp_path: Path) -> dict:
    original = tmp_path / "original"
    original.mkdir()
    (original / "SKILL.md").write_bytes(b"Original faulty rule.\n")
    submission_base = tmp_path / "submission"
    for name, body in FINAL_FILES.items():
        destination = submission_base / "final" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(body)
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    case = {
        "original": original,
        "submission_base": submission_base,
        "jobs": jobs,
        "gold_path": tmp_path / "gold.json",
        "submission_path": submission_base / "submission.json",
        "judgments_path": tmp_path / "judgments.json",
        "submission": {
            "method_id": "method-a",
            "benchmark_version": "v1",
            "tasks": [
                {
                    "task_id": "t",
                    "diagnoses": [],
                    "repaired_bundle": "final",
                }
            ],
        },
    }
    write_json(
        case["gold_path"],
        {
            "benchmark_version": "v1",
            "tasks": [
                {
                    "task_id": "t",
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
            ],
        },
    )
    write_json(case["submission_path"], case["submission"])
    write_json(
        case["judgments_path"],
        {
            "method_id": "method-a",
            "benchmark_version": "v1",
            "prompt_version": "skill-diagnosis-repair-v2.1",
            "judge_model": "offline-fixture",
            "tasks": [
                {
                    "task_id": "t",
                    "diagnosis_result": {"diagnoses": []},
                    "repair_result": {
                        "repairs": [
                            {
                                "defect_id": "D1",
                                "repair_present": True,
                                "repair_correct": True,
                                "confidence": 0.99,
                                "reason": "Required final behavior is present.",
                            }
                        ],
                        "extra_modifications": [],
                        "regression": {
                            "substantive_change": True,
                            "detected": False,
                            "new_defects": [],
                            "confidence": 0.99,
                            "reason": "Other behavior retained.",
                        },
                    },
                }
            ],
        },
    )
    return case


def add_run(
    case: dict,
    run_id: str,
    *,
    condition: str = "method-skill",
    passed: bool = True,
    method: str = "method-a",
    task: str = "t",
    digest: str = FINAL_SHA,
    has_report: bool = True,
) -> Path:
    directory = case["jobs"] / method / task / run_id
    original = condition == "original-skill"
    if original:
        digest = ORIGINAL_SHA
    request = {
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
        "task_id": task,
        "method_id": method,
        "rollout_id": run_id,
        "stage": "final",
        "condition": condition,
        "skill_bundle": None if original else str(case["submission_base"] / "final"),
        "skill_bundle_manifest": None if original else {"skill_bundle_sha256": digest},
    }
    write_json(directory / "executor_request.json", request)
    if has_report:
        write_json(
            directory / "benchmark_result.json",
            {
                "task_id": task,
                "method_id": method,
                "rollout_id": run_id,
                "stage": "final",
                "protocol_id": "skillrepair-v1",
                "protocol_version": 2,
                "model": "openai/gpt-5.5",
                "reasoning_effort": "medium",
                "provider_route": "openrouter",
                "execution_ok": True,
                "task_passed": passed,
                "reward": 1.0 if passed else 0.0,
                "protocol_evidence_valid": True,
                "trajectory_complete": True,
                "iteration_accounting_complete": True,
                "skill_exposure_verified": True,
                "error": None,
                "verifier_error": None,
                "export_error": None,
                "termination_reason": "LOCAL_VERIFIER_PRIVATE_TOKEN",
                "result_json": str(directory / "result.json"),
            },
        )
    if original:
        shutil.copytree(case["original"], directory / "inputs" / "skills")
        write_json(
            directory / "result.json",
            {
                "task_name": task,
                "rollout_name": run_id,
                "rewards": {"reward": 1.0 if passed else 0.0},
                "executor": {
                    "evaluation_condition": "original-skill",
                    "skill_context_preloaded": True,
                    "skill_bundle_sha256": digest,
                    "prompt_runs": [
                        {
                            "prompt_ordinal": index,
                            "skill_context_preloaded": True,
                            "skill_bundle_sha256": digest,
                        }
                        for index in (0, 1)
                    ],
                },
            },
        )
    return directory


def arguments(
    case: dict, output: Path, *, directory: Path | None = None, execute: bool = False
) -> list[str]:
    args = [
        "--gold",
        str(case["gold_path"]),
        "--submission",
        str(case["submission_path"]),
        "--output",
        str(output),
        "--executor-runs-dir",
        str(directory or case["jobs"]),
    ]
    if execute:
        return [
            *args,
            "--execute",
            "--judge-model",
            "mock-model",
            "--api-key-env",
            "LOCAL_EVALUATION_TEST_KEY",
        ]
    return [*args, "--judge-responses", str(case["judgments_path"])]


@pytest.mark.parametrize(
    "method_directory", [False, True], ids=["jobs-root", "method-directory"]
)
def test_local_results_generate_all_reports_without_handwritten_manifests(
    local_case: dict,
    tmp_path: Path,
    method_directory: bool,
) -> None:
    case = local_case
    run = add_run(case, "final-r1")
    output = tmp_path / "local-report"
    directory = case["jobs"] / "method-a" if method_directory else case["jobs"]

    assert evaluator.main(arguments(case, output, directory=directory)) == 0

    summary = read_json(output / "summary.json")
    assert summary["evidence_policy"] == "local_executor_artifacts"
    assert summary["original_pass_policy"] == "local_executor_verified_skip"
    assert summary["verified_fix_rate"] == summary["verified_fix_coverage"] == 1.0
    assert summary["verified_fix_status"] == "complete"
    assert summary["metrics"]["repair"]["f1"] == 1.0
    generated = read_json(output / "executor-results.json")
    assert generated["method_id"] == "method-a"
    assert generated["benchmark_version"] == "v1"
    assert len(generated["tasks"]) == 1
    assert generated["tasks"][0]["task_id"] == "t"
    assert (output / generated["tasks"][0]["benchmark_result"]).resolve() == (
        run / "benchmark_result.json"
    ).resolve()
    assert (
        read_json(output / "verifier_results.json")["tasks"][0]["rollout_id"]
        == "final-r1"
    )
    requests = (output / "requests.jsonl").read_text(encoding="utf-8")
    assert "LOCAL_VERIFIER_PRIVATE_TOKEN" not in requests
    for line in requests.splitlines():
        payload = json.loads(json.loads(line)["messages"][1]["content"])
        assert "verified_fix_rate" not in payload and "executor-results" not in payload


def test_unrelated_runs_and_old_final_hashes_do_not_compete_with_current_final(
    local_case: dict, tmp_path: Path
) -> None:
    case = local_case
    add_run(case, "correct", passed=False)
    add_run(case, "other-method", method="method-b")
    add_run(case, "other-task", task="another-task")
    add_run(case, "no-skill", condition="no-skill")
    add_run(case, "old-final", digest="sha256:" + "0" * 64)
    output = tmp_path / "only-current-final"

    assert evaluator.main(arguments(case, output)) == 0

    assert read_json(output / "summary.json")["verified_fix_rate"] == 0.0
    assert (
        read_json(output / "verifier_results.json")["tasks"][0]["rollout_id"]
        == "correct"
    )


@pytest.mark.parametrize(
    "has_second_report", [True, False], ids=["pass-and-fail", "pass-and-request-only"]
)
def test_multiple_matching_runs_are_ambiguous_instead_of_selecting_success_or_latest(
    local_case: dict,
    tmp_path: Path,
    has_second_report: bool,
) -> None:
    case = local_case
    add_run(case, "first", passed=True)
    add_run(case, "second", passed=False, has_report=has_second_report)

    assert evaluator.main(arguments(case, tmp_path / "ambiguous", execute=True)) == 2


def test_explicit_run_selects_the_failed_attempt_without_success_bias(
    local_case: dict, tmp_path: Path
) -> None:
    case = local_case
    add_run(case, "passed-round")
    add_run(case, "failed-round", passed=False)
    case["submission"]["tasks"][0]["executor_run_id"] = "failed-round"
    write_json(case["submission_path"], case["submission"])
    output = tmp_path / "explicit-failed-round"

    assert evaluator.main(arguments(case, output)) == 0

    assert read_json(output / "summary.json")["verified_fix_rate"] == 0.0
    assert (
        read_json(output / "verifier_results.json")["tasks"][0]["rollout_id"]
        == "failed-round"
    )


@pytest.mark.parametrize("invalid", ["missing-id", "different-final"])
def test_explicit_run_errors_are_not_silently_ignored(
    local_case: dict, tmp_path: Path, invalid: str
) -> None:
    case = local_case
    add_run(case, "current")
    if invalid == "different-final":
        add_run(case, "selected", digest="sha256:" + "0" * 64)
    case["submission"]["tasks"][0]["executor_run_id"] = "selected"
    write_json(case["submission_path"], case["submission"])

    assert (
        evaluator.main(arguments(case, tmp_path / "bad-explicit-run", execute=True))
        == 2
    )


@pytest.mark.parametrize(
    "request_only", [False, True], ids=["no-matching-run", "request-without-report"]
)
def test_absent_result_is_missing_not_passed(
    local_case: dict, tmp_path: Path, request_only: bool
) -> None:
    case = local_case
    if request_only:
        add_run(case, "unfinished", has_report=False)
    output = tmp_path / "missing-result"

    assert evaluator.main(arguments(case, output)) == 0

    summary = read_json(output / "summary.json")
    assert summary["verified_fix_rate"] is None
    assert summary["verified_fix_missing_task_count"] == 1
    assert summary["verified_fix_coverage"] == 0.0
    assert (
        read_json(output / "verifier_results.json")["tasks"][0]["status"]
        == "missing_result"
    )
    generated = read_json(output / "executor-results.json")
    assert generated["tasks"] == []
    if request_only:
        assert generated["missing_runs"][0]["task_id"] == "t"
        assert generated["missing_runs"][0]["rollout_id"] == "unfinished"
        assert generated["missing_runs"][0]["executor_request"]


def mark_original_pass(case: dict, run_id: str = "original-r1") -> Path:
    case["submission"]["tasks"] = [
        {"task_id": "t", "original_pass": True, "original_run_id": run_id}
    ]
    write_json(case["submission_path"], case["submission"])
    return add_run(case, run_id, condition="original-skill")


def test_original_pass_uses_local_raw_evidence_and_snapshot_without_allowlist_or_model(
    local_case: dict,
    tmp_path: Path,
) -> None:
    case = local_case
    mark_original_pass(case)
    output = tmp_path / "original-pass"
    args = arguments(case, output)
    args = args[: args.index("--judge-responses")]

    assert evaluator.main([*args, "--execute"]) == 0

    summary = read_json(output / "summary.json")
    assert summary["status"] == "complete"
    assert summary["metrics"] is None
    assert summary["verified_fix_rate"] is None
    assert summary["verified_fix_status"] == "no_eligible_tasks"
    assert summary["skipped_original_pass_task_count"] == 1
    assert summary["evaluated_task_count"] == 0
    assert summary["evidence_policy"] == "local_executor_artifacts"
    skipped = read_json(output / "skipped_tasks.json")["tasks"][0]
    assert skipped["original_run"]["source"] == "local_executor"
    assert skipped["original_run"]["run_id"] == "original-r1"
    assert (output / "requests.jsonl").read_text(encoding="utf-8").strip() == ""


@pytest.mark.parametrize(
    "invalid",
    [
        "failed-report",
        "missing-raw",
        "raw-task",
        "raw-run",
        "raw-reward",
        "raw-condition",
        "executor-sha",
        "prompt-sha",
        "not-preloaded",
        "empty-prompts",
        "missing-snapshot",
        "changed-snapshot",
    ],
)
def test_original_pass_needs_consistent_real_run_and_original_input_snapshot(
    local_case: dict,
    tmp_path: Path,
    invalid: str,
) -> None:
    case = local_case
    run = mark_original_pass(case)
    raw_path = run / "result.json"
    raw = read_json(raw_path)
    if invalid == "failed-report":
        report = read_json(run / "benchmark_result.json")
        report.update(task_passed=False, reward=0.0)
        write_json(run / "benchmark_result.json", report)
    elif invalid == "raw-task":
        raw["task_name"] = "other-task"
    elif invalid == "raw-run":
        raw["rollout_name"] = "other-run"
    elif invalid == "raw-reward":
        raw["rewards"]["reward"] = 0.0
    elif invalid == "raw-condition":
        raw["executor"]["evaluation_condition"] = "method-skill"
    elif invalid == "executor-sha":
        raw["executor"]["skill_bundle_sha256"] = FINAL_SHA
    elif invalid == "prompt-sha":
        raw["executor"]["prompt_runs"][1]["skill_bundle_sha256"] = FINAL_SHA
    elif invalid == "not-preloaded":
        raw["executor"]["prompt_runs"][1]["skill_context_preloaded"] = False
    elif invalid == "empty-prompts":
        raw["executor"]["prompt_runs"] = []
    elif invalid == "missing-snapshot":
        (run / "inputs" / "skills" / "SKILL.md").unlink()
        (run / "inputs" / "skills").rmdir()
    elif invalid == "changed-snapshot":
        (run / "inputs" / "skills" / "SKILL.md").write_text(
            "A different original snapshot.\n", encoding="utf-8"
        )
    write_json(raw_path, raw)
    if invalid == "missing-raw":
        raw_path.unlink()

    assert (
        evaluator.main(arguments(case, tmp_path / "invalid-original", execute=True))
        == 2
    )


@pytest.mark.parametrize(
    "legacy_option", ["--executor-results", "--verified-original-passes"]
)
def test_local_mode_cannot_mix_with_external_manifest_options(
    local_case: dict, tmp_path: Path, legacy_option: str
) -> None:
    case = local_case
    manifest = tmp_path / "legacy.json"
    write_json(manifest, {})
    args = [
        *arguments(case, tmp_path / "mixed-modes", execute=True),
        legacy_option,
        str(manifest),
    ]
    try:
        exit_code = evaluator.main(args)
    except SystemExit as exc:
        exit_code = exc.code
    assert exit_code == 2
