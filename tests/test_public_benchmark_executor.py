from __future__ import annotations

import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from benchflow.benchmark_executor import (
    BENCHFLOW_BASE_COMMIT,
    EXECUTOR_PROTOCOL_ID,
    EXECUTOR_SKILL_EXPOSURE_MODE,
    protocol_descriptor,
)
from benchmark_executor import BenchmarkExecutor


def _task_root(tmp_path: Path) -> Path:
    task = tmp_path / "tasks" / "task-a"
    task.mkdir(parents=True)
    (task / "instruction.md").write_text("Solve the task.\n")
    return task.parent


def _bundle(tmp_path: Path) -> Path:
    bundle = tmp_path / "bundle" / "main"
    bundle.mkdir(parents=True)
    (bundle / "SKILL.md").write_text("# Procedure\nDo the work.\n")
    return bundle.parent


def _install_fake_rollout(
    monkeypatch: pytest.MonkeyPatch,
    *,
    reward: float | None = 1.0,
    verifier_error: str | None = None,
    verifier_error_category: str | None = None,
) -> list[object]:
    captured: list[object] = []

    async def fake_run(config):
        captured.append(config)
        rollout_dir = Path(config.jobs_dir) / config.job_name / config.rollout_name
        request = json.loads((rollout_dir / "executor_request.json").read_text())
        bundle = request["skill_bundle_manifest"]
        bundle_sha = bundle["skill_bundle_sha256"]
        skill_count = bundle["preloaded_skill_count"]
        executor = {
            "protocol_id": EXECUTOR_PROTOCOL_ID,
            "protocol_version": 1,
            "benchflow_base_commit": BENCHFLOW_BASE_COMMIT,
            "agent": "openhands",
            "model": config.model,
            "provider_route": request["model_selection"]["provider_route"],
            "provider_base_url": "https://api.deepseek.com/v1",
            "provider_protocol": "openai-completions",
            "skill_exposure_mode": EXECUTOR_SKILL_EXPOSURE_MODE,
            "max_parent_iterations_per_step": 60,
            "evaluation_condition": "method-skill",
            "skill_context_preloaded": True,
            "skill_bundle_sha256": bundle_sha,
            "preloaded_skill_count": skill_count,
            "iteration_accounting_complete": True,
            "stop_reason": "end_turn",
            "prompt_runs": [
                {
                    "prompt_ordinal": 1,
                    "stop_reason": "end_turn",
                    "acp_stop_reason": "end_turn",
                    "iterations_used": 12,
                    "max_iterations": 60,
                    "skill_context_preloaded": True,
                    "skill_bundle_sha256": bundle_sha,
                    "preloaded_skill_count": skill_count,
                }
            ],
        }
        (rollout_dir / "trajectory").mkdir(exist_ok=True)
        (rollout_dir / "verifier").mkdir(exist_ok=True)
        (rollout_dir / "artifacts").mkdir(exist_ok=True)
        (rollout_dir / "trajectory" / "acp_trajectory.jsonl").write_text(
            json.dumps({"type": "agent_message", "text": "done"}) + "\n"
        )
        (rollout_dir / "trajectory" / "llm_trajectory.jsonl").write_text(
            json.dumps({"request": {}, "response": {}})
            + "\n"
            + json.dumps({"request": {}, "response": {}})
            + "\n"
        )
        (rollout_dir / "config.json").write_text(
            json.dumps(
                {
                    "agent": "openhands",
                    "model": config.model,
                    "reasoning_effort": config.reasoning_effort,
                    "environment": config.environment,
                    "task_digest": config.task_digest,
                    "executor": executor,
                }
            )
        )
        rewards = {"reward": reward, "subtest": reward} if reward is not None else None
        (rollout_dir / "result.json").write_text(
            json.dumps(
                {
                    "task_name": config.task_path.name,
                    "rollout_name": config.rollout_name,
                    "rewards": rewards,
                    "agent": "openhands",
                    "model": config.model,
                    "n_skill_invocations": 0,
                    "agent_result": {
                        "iterations_used": 12,
                        "cost_usd": 0.25,
                        "stop_reason": "end_turn",
                    },
                    "error": None,
                    "error_category": None,
                    "verifier_error": verifier_error,
                    "verifier_error_category": verifier_error_category,
                    "export_error": None,
                    "partial_trajectory": False,
                    "timing": {"total": 123.4},
                    "executor": executor,
                }
            )
        )
        return SimpleNamespace(rollout_name=config.rollout_name)

    monkeypatch.setattr("benchmark_executor.executor.bf.run", fake_run)
    return captured


def test_public_api_uses_selected_model_route_and_shared_rollout_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Guards protocol v1 on base aadad44: model routing is instance-scoped."""
    tasks_root = _task_root(tmp_path)
    bundle = _bundle(tmp_path)
    captured = _install_fake_rollout(monkeypatch)
    executor = BenchmarkExecutor(
        tasks_root=tasks_root,
        jobs_root=tmp_path / "jobs",
        model="deepseek/deepseek-chat",
        reasoning_effort="high",
    )

    result = executor.run(
        task_id="task-a",
        condition="method-skill",
        skill_bundle=bundle,
        method_id="skillrevise",
        stage="round-2",
        rollout_id="task-a-r2",
    )

    assert len(captured) == 1
    config = captured[0]
    assert config.model == "deepseek/deepseek-chat"
    assert config.reasoning_effort == "high"
    assert config.environment == "docker"
    assert config.skills_dir == bundle.resolve()
    assert result.model == "deepseek/deepseek-chat"
    assert result.provider_route == "deepseek"
    assert result.provider_base_url == "https://api.deepseek.com/v1"
    assert result.provider_protocol == "openai-completions"
    assert result.task_passed is True
    assert result.success is True
    assert result.execution_ok is True
    assert result.comparable is True
    assert result.agent_iterations == 12
    assert result.provider_requests == 2
    assert result.skill_exposure.verified is True
    assert result.skill_exposure.native_skill_invocations == 0
    assert result.verifier_components == {"subtest": 1.0}
    assert result.wall_time_sec == 123.4
    assert result.cost_usd == 0.25
    assert result.artifacts.request_json.is_file()
    summary_path = result.artifacts.rollout_dir / "benchmark_result.json"
    assert summary_path.is_file()
    summary = json.loads(summary_path.read_text())
    assert summary["verifier_error"] is None
    assert summary["verifier_error_category"] is None
    assert summary["protocol_evidence_valid"] is True
    assert summary["skill_exposure_verified"] is True


def test_public_result_excludes_verifier_dep_install_from_comparison(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unscored verifier bootstrap failure stays visible and non-comparable."""
    tasks_root = _task_root(tmp_path)
    _install_fake_rollout(
        monkeypatch,
        reward=None,
        verifier_error=(
            "verifier crashed: dependency install failed "
            "(see verifier/test-stdout.txt in the run artifacts for resolver output)"
        ),
        verifier_error_category="verifier_dep_install",
    )
    executor = BenchmarkExecutor(
        tasks_root=tasks_root,
        jobs_root=tmp_path / "jobs",
        model="openrouter/openai/gpt-5.2",
    )

    result = executor.run(
        task_id="task-a",
        condition="method-skill",
        skill_bundle=_bundle(tmp_path),
        method_id="machine-smoke",
        stage="original-skill-smoke",
        rollout_id="task-a-verifier-dep-install",
    )

    assert result.reward is None
    assert result.task_passed is None
    assert result.execution_ok is False
    assert result.comparable is False
    assert result.verifier_error_category == "verifier_dep_install"
    summary = json.loads(
        (result.artifacts.rollout_dir / "benchmark_result.json").read_text()
    )
    assert summary["task_passed"] is None
    assert summary["execution_ok"] is False
    assert summary["comparable"] is False
    assert summary["verifier_error_category"] == "verifier_dep_install"


def test_public_api_does_not_allow_per_rollout_model_or_budget_override() -> None:
    """Guards protocol v1 on base aadad44: methods cannot drift core settings."""
    parameters = inspect.signature(BenchmarkExecutor.run).parameters

    assert "model" not in parameters
    assert "provider" not in parameters
    assert "max_iterations" not in parameters
    assert "timeout" not in parameters
    assert "agent" not in parameters
    assert "prompt" not in parameters


@pytest.mark.asyncio
async def test_public_api_validates_condition_bundle_and_running_loop(
    tmp_path: Path,
) -> None:
    """Guards protocol v1 on base aadad44: invalid calls fail before rollout."""
    executor = BenchmarkExecutor(
        tasks_root=_task_root(tmp_path),
        jobs_root=tmp_path / "jobs",
        model="openrouter/openai/gpt-5.2",
    )

    with pytest.raises(ValueError, match="requires a complete skill_bundle"):
        await executor.run_async(
            task_id="task-a",
            condition="method-skill",
            skill_bundle=None,
            method_id="method",
            stage="round-1",
            rollout_id="missing-bundle",
        )
    with pytest.raises(RuntimeError, match="run_async"):
        executor.run(
            task_id="task-a",
            condition="original-skill",
            method_id="method",
            stage="baseline",
            rollout_id="inside-loop",
        )


def test_public_api_rejects_unknown_protocol_and_existing_output(
    tmp_path: Path,
) -> None:
    """Guards protocol v1 on base aadad44: protocol and output identity fail closed."""
    tasks_root = _task_root(tmp_path)
    with pytest.raises(ValueError, match="unsupported executor protocol"):
        BenchmarkExecutor(
            tasks_root=tasks_root,
            jobs_root=tmp_path / "jobs",
            model="openai/gpt-5.2",
            protocol="method-private-v2",
        )

    normalized = BenchmarkExecutor(
        tasks_root=tasks_root,
        jobs_root=tmp_path / "normalized-jobs",
        model="openai/gpt-5.2",
        reasoning_effort=" High ",
    )
    assert normalized.reasoning_effort == "high"

    executor = BenchmarkExecutor(
        tasks_root=tasks_root,
        jobs_root=tmp_path / "jobs",
        model="openai/gpt-5.2",
    )
    existing = tmp_path / "jobs" / "method" / "same-id"
    existing.mkdir(parents=True)
    with pytest.raises(FileExistsError):
        executor.run(
            task_id="task-a",
            condition="original-skill",
            method_id="method",
            stage="baseline",
            rollout_id="same-id",
        )


def test_version_descriptor_keeps_model_outside_execution_protocol() -> None:
    """Guards protocol v1 on base aadad44: models/providers remain swappable."""
    version_path = Path(__file__).parents[1] / "BENCHMARK_EXECUTOR_VERSION.json"
    version = json.loads(version_path.read_text())

    assert version == protocol_descriptor()
    assert version["protocol_id"] == "skillrepair-v1"
    assert "model" not in version
    assert "openrouter/openai/gpt-5.2" not in json.dumps(version)
    assert version["model_policy"].startswith("selected once")


def test_delivery_guide_uses_executor_root_for_both_install_paths() -> None:
    guide = (Path(__file__).parents[1] / "DELIVERY_GUIDE.md").read_text(
        encoding="utf-8"
    )

    assert 'export EXECUTOR_ROOT="$HOME/benchmark-executor"' in guide
    assert 'export EXECUTOR_ROOT="$EXECUTOR_HOME/benchmark-executor"' in guide
    assert guide.count('cd "$EXECUTOR_ROOT"') >= 3
    assert 'cd "$EXECUTOR_HOME/benchmark-executor"' not in guide
