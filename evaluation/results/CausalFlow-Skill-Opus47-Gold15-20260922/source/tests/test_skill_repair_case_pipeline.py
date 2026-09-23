from __future__ import annotations

import json
from pathlib import Path

import pytest

from repro_wrappers.defects.build_skill_repair_cases import (
    CaseBuildError,
    build_case_registries,
    skill_bundle_digest,
)
from repro_wrappers.defects.evaluate_skill_repair_submission import (
    SubmissionError,
    evaluate_submission,
    prepare_execution_environment,
    validate_external_repaired_bundle,
)
from repro_wrappers.defects.score_defective_skill_evaluation import score_evaluation


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _rollout(
    jobs: Path,
    rollout_id: str,
    *,
    task_id: str,
    reward: float,
    skill_bundle_sha256: str | None = None,
    model: str = "openrouter/openai/gpt-5.2",
) -> Path:
    root = jobs / "defective-skill-eval" / rollout_id
    benchmark = {
        "protocol_id": "skillrepair-v1",
        "model": model,
        "reasoning_effort": "high",
        "task_id": task_id,
        "rollout_id": rollout_id,
        "reward": reward,
        "task_passed": reward >= 1.0,
        "execution_ok": True,
        "comparable": True,
        "trajectory_complete": True,
    }
    _write_json(root / "benchmark_result.json", benchmark)
    _write_json(
        root / "result.json",
        {
            "task_name": task_id,
            "rollout_name": rollout_id,
            "task_digest": "sha256:task",
            "rewards": {"reward": reward},
            "executor": {
                "skill_bundle_sha256": skill_bundle_sha256,
                "evaluation_condition": (
                    "method-skill" if skill_bundle_sha256 else "original-skill"
                ),
            },
        },
    )
    _write_json(root / "prompts.json", {"prompts": ["do the task"]})
    _write_json(root / "config.json", {"rollout_name": rollout_id})
    trajectory = root / "trajectory"
    trajectory.mkdir(parents=True)
    (trajectory / "acp_trajectory.jsonl").write_text(
        json.dumps({"type": "agent_message", "text": rollout_id}) + "\n",
        encoding="utf-8",
    )
    (trajectory / "llm_trajectory.jsonl").write_text(
        json.dumps({"request": {}, "response": {}}) + "\n",
        encoding="utf-8",
    )
    # This evidence must never enter the public package.
    _write_json(root / "verifier" / "hidden-answer.json", {"answer": 42})
    return root


def _source_files(tmp_path: Path) -> dict[str, Path]:
    variant_id = "skill-secret-defect-description-v1"
    task_id = "task-a"
    bundles = tmp_path / "bundles"
    bundle = bundles / variant_id / "bundle" / "example-skill"
    bundle.mkdir(parents=True)
    (bundle / "SKILL.md").write_text("# Skill\nwrong rule\n", encoding="utf-8")
    ground_truth = bundles / variant_id / "ground_truth" / "defect_manifest.json"
    _write_json(
        ground_truth,
        {
            "variant_id": variant_id,
            "task_id": task_id,
            "target_skill": "example-skill",
            "target_file": "example-skill/SKILL.md",
            "defect_type": "logic_error",
            "annotation": {
                "locations": [{"original_spans": [{"start_line": 2, "end_line": 2}]}]
            },
            "integrity": {
                "original_bundle_manifest": {},
                "defective_bundle_manifest": {},
            },
        },
    )
    jobs = tmp_path / "jobs"
    _rollout(jobs, "task-a-clean-r0", task_id=task_id, reward=1.0)
    _rollout(
        jobs,
        f"{variant_id}-r0",
        task_id=task_id,
        reward=0.0,
        skill_bundle_sha256=f"sha256:{skill_bundle_digest(bundle.parent)}",
    )

    manifest = tmp_path / "manifest.json"
    _write_json(
        manifest,
        {
            "schema": "causalflow.defective-skill-construction.v1",
            "source": {"skillsbench_commit": "abc123"},
            "variants": [{"variant_id": variant_id, "task_id": task_id}],
        },
    )
    plan = tmp_path / "plan.json"
    _write_json(
        plan,
        {
            "schema": "causalflow.defective-skill-run-plan.v1",
            "source_manifest": str(manifest.resolve()),
            "protocol_id": "skillrepair-v1",
            "model": "openrouter/openai/gpt-5.2",
            "runs": [
                {
                    "arm": "clean",
                    "task_id": task_id,
                    "variant_id": None,
                    "trial": 0,
                    "rollout_id": "task-a-clean-r0",
                },
                {
                    "arm": "defective",
                    "task_id": task_id,
                    "variant_id": variant_id,
                    "trial": 0,
                    "rollout_id": f"{variant_id}-r0",
                },
            ],
        },
    )
    summary = tmp_path / "summary.json"
    _write_json(
        summary,
        {
            "schema": "causalflow.defective-skill-matrix-summary.v1",
            "source_plan": str(plan.resolve()),
            "protocol_id": "skillrepair-v1",
            "model": "openrouter/openai/gpt-5.2",
            "variants": [
                {
                    "variant_id": variant_id,
                    "status": "effective",
                    "pilot_gate": {"effective": True},
                }
            ],
        },
    )
    return {
        "manifest": manifest,
        "plan": plan,
        "summary": summary,
        "bundles": bundles,
        "jobs": jobs,
        "ground_truth": ground_truth,
    }


def _build(tmp_path: Path) -> tuple[dict, dict, Path, Path]:
    paths = _source_files(tmp_path)
    public_root = tmp_path / "public"
    private_path = tmp_path / "private" / "registry.json"
    public, private = build_case_registries(
        manifest_path=paths["manifest"],
        plan_path=paths["plan"],
        summary_path=paths["summary"],
        bundles_root=paths["bundles"],
        jobs_root=paths["jobs"],
        public_root=public_root,
        private_registry_path=private_path,
    )
    return public, private, public_root, private_path


def test_public_case_is_opaque_and_excludes_ground_truth_and_verifier(tmp_path: Path):
    public, private, public_root, _ = _build(tmp_path)

    assert public["case_count"] == 1
    case_id = public["cases"][0]["case_id"]
    assert case_id.startswith("dsr-")
    case_dir = public_root / "cases" / case_id
    public_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in case_dir.rglob("*")
        if path.is_file()
    )
    assert "skill-secret-defect-description-v1" not in public_text
    assert not (case_dir / "ground_truth").exists()
    assert not (case_dir / "evidence" / "verifier").exists()
    assert (case_dir / "bundle" / "example-skill" / "SKILL.md").is_file()
    assert private["cases"][0]["variant_id"] == "skill-secret-defect-description-v1"


def test_case_builder_refuses_non_effective_summary(tmp_path: Path):
    paths = _source_files(tmp_path)
    summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
    summary["variants"][0]["status"] = "ineffective"
    summary["variants"][0]["pilot_gate"]["effective"] = False
    _write_json(paths["summary"], summary)

    with pytest.raises(CaseBuildError, match="no effective variants"):
        build_case_registries(
            manifest_path=paths["manifest"],
            plan_path=paths["plan"],
            summary_path=paths["summary"],
            bundles_root=paths["bundles"],
            jobs_root=paths["jobs"],
            public_root=tmp_path / "public",
            private_registry_path=tmp_path / "private.json",
        )


def test_submission_preflight_validates_case_diagnosis_and_full_bundle(tmp_path: Path):
    public, _, public_root, private_path = _build(tmp_path)
    case_id = public["cases"][0]["case_id"]
    case_dir = public_root / "cases" / case_id
    diagnosis = tmp_path / "diagnosis.json"
    _write_json(
        diagnosis,
        {
            "schema": "causalflow.skill-defect-diagnosis.v1",
            "case_id": case_id,
            "method_id": "method-a",
            "predictions": [],
            "accounting": {"diagnosis_seconds": 1.0, "diagnosis_cost_usd": 0.0},
        },
    )

    plan = evaluate_submission(
        case_dir=case_dir,
        private_registry_path=private_path,
        diagnosis_path=diagnosis,
        repaired_bundle=case_dir / "bundle",
        method_id="method-a",
        tasks_root=None,
        jobs_root=None,
        trial=0,
        execute=False,
        repair_result_path=None,
        verifier_proxy_mode="off",
        output=None,
    )

    assert plan["status"] == "preflight_ok"
    assert plan["case_id"] == case_id
    assert plan["repaired_bundle_sha256"].startswith("sha256:")


def test_execution_environment_matches_matrix_runner(monkeypatch):
    calls: list[tuple[str, str | None]] = []
    monkeypatch.setattr(
        "repro_wrappers.defects.evaluate_skill_repair_submission.normalize_host_environment",
        lambda: calls.append(("normalize", None)),
    )
    monkeypatch.setattr(
        "repro_wrappers.defects.evaluate_skill_repair_submission.configure_docker_install_proxy",
        lambda: calls.append(("install_proxy", None)),
    )
    monkeypatch.setattr(
        "repro_wrappers.defects.evaluate_skill_repair_submission.configure_verifier_proxy",
        lambda mode: calls.append(("verifier_proxy", mode)),
    )

    prepare_execution_environment("explicit")

    assert calls == [
        ("normalize", None),
        ("install_proxy", None),
        ("verifier_proxy", "explicit"),
    ]


def test_repair_submission_must_not_alias_task_bundled_skills(tmp_path: Path):
    tasks = tmp_path / "tasks"
    original = tasks / "task-a" / "environment" / "skills"
    original.mkdir(parents=True)
    external = tmp_path / "method-output" / "skills"
    external.mkdir(parents=True)

    with pytest.raises(SubmissionError, match="external method output"):
        validate_external_repaired_bundle(
            original, tasks_root=tasks, task_id="task-a"
        )

    validate_external_repaired_bundle(external, tasks_root=tasks, task_id="task-a")


def test_submission_preflight_rejects_tampered_case_payload(tmp_path: Path):
    public, _, public_root, private_path = _build(tmp_path)
    case_id = public["cases"][0]["case_id"]
    case_dir = public_root / "cases" / case_id
    (case_dir / "bundle" / "example-skill" / "SKILL.md").write_text(
        "tampered\n", encoding="utf-8"
    )
    diagnosis = tmp_path / "diagnosis.json"
    _write_json(
        diagnosis,
        {
            "schema": "causalflow.skill-defect-diagnosis.v1",
            "case_id": case_id,
            "method_id": "method-a",
            "predictions": [],
            "accounting": {"diagnosis_seconds": 0, "diagnosis_cost_usd": 0},
        },
    )

    with pytest.raises(SubmissionError, match="hash mismatch"):
        evaluate_submission(
            case_dir=case_dir,
            private_registry_path=private_path,
            diagnosis_path=diagnosis,
            repaired_bundle=case_dir / "bundle",
            method_id="method-a",
            tasks_root=None,
            jobs_root=None,
            trial=0,
            execute=False,
            repair_result_path=None,
            verifier_proxy_mode="off",
            output=None,
        )


def test_common_score_reports_recovery_ratio():
    ground_truth = {
        "variant_id": "v",
        "task_id": "t",
        "target_skill": "s",
        "target_file": "s/SKILL.md",
        "defect_type": "logic_error",
        "annotation": {"locations": [{"original_spans": [{"start_line": 1, "end_line": 1}]}]},
        "integrity": {
            "original_bundle_manifest": {},
            "defective_bundle_manifest": {},
        },
    }

    score = score_evaluation(
        ground_truth=ground_truth,
        diagnosis=None,
        clean_reward=1.0,
        defective_reward=0.0,
        repair_reward=0.75,
        repaired_bundle=None,
    )

    assert score["reward"]["repair_gain"] == 0.75
    assert score["reward"]["recovery_ratio"] == 0.75
    assert score["reward"]["repair_task_passed"] is False
