from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from benchflow.acp.runtime import execute_prompts
from benchflow.acp.session import ACPSession
from benchflow.benchmark_executor import (
    BENCHFLOW_BASE_COMMIT,
    ENV_DISABLE_SUBAGENTS,
    ENV_LLM_TIMEOUT,
    ENV_MAX_ITERATIONS,
    ENV_SKILLS_ROOT,
    MAX_PARENT_ITERATIONS_PER_STEP,
    OPENHANDS_CLI_COMMIT,
    apply_openhands_executor_env,
    build_skill_bundle_manifest,
    executor_metadata,
    executor_result_metadata,
    protocol_descriptor,
    snapshot_skill_bundle,
    validate_method_skill_task_count,
    validate_openhands_executor_agent_env,
    validate_openhands_executor_model,
    validate_openhands_executor_scenes,
)
from benchflow.skill_policy import resolve_task_skill_policy


def _bundle(root: Path) -> Path:
    skills = root / "skills"
    (skills / "zeta" / "scripts").mkdir(parents=True)
    (skills / "alpha").mkdir()
    (skills / "zeta" / "SKILL.md").write_text("zeta body\n")
    (skills / "alpha" / "SKILL.md").write_text("alpha body\n")
    (skills / "zeta" / "scripts" / "solve.py").write_text("print('ok')\n")
    return skills


def test_bundle_snapshot_is_complete_and_deterministic(tmp_path: Path) -> None:
    """Guards protocol v1 on base aadad44: rollout bundles are frozen exactly."""
    source = _bundle(tmp_path / "source")
    first = build_skill_bundle_manifest(source)
    snapshot = tmp_path / "run" / "inputs" / "skills"

    copied = snapshot_skill_bundle(source, snapshot)

    assert copied == first
    assert copied.skill_files == ("alpha/SKILL.md", "zeta/SKILL.md")
    assert copied.file_count == 3
    assert (snapshot / "zeta" / "scripts" / "solve.py").is_file()

    (source / "zeta" / "scripts" / "solve.py").write_text("print('changed')\n")
    assert build_skill_bundle_manifest(source).sha256 != first.sha256


def test_bundle_rejects_empty_missing_utf8_and_symlink(tmp_path: Path) -> None:
    """Guards protocol v1 on base aadad44: invalid bundles fail before rollout."""
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="empty"):
        build_skill_bundle_manifest(empty)

    no_skill = tmp_path / "no-skill"
    no_skill.mkdir()
    (no_skill / "helper.py").write_text("pass")
    with pytest.raises(ValueError, match=r"no SKILL\.md"):
        build_skill_bundle_manifest(no_skill)

    invalid = tmp_path / "invalid" / "one"
    invalid.mkdir(parents=True)
    (invalid / "SKILL.md").write_bytes(b"\xff")
    with pytest.raises(ValueError, match="UTF-8"):
        build_skill_bundle_manifest(invalid.parent)

    if hasattr(Path, "symlink_to"):
        linked_root = tmp_path / "linked"
        (linked_root / "one").mkdir(parents=True)
        target = tmp_path / "target.md"
        target.write_text("body")
        try:
            (linked_root / "one" / "SKILL.md").symlink_to(target)
        except OSError:
            pytest.skip("symlinks are unavailable on this platform")
        with pytest.raises(ValueError, match="symlink"):
            build_skill_bundle_manifest(linked_root)


def test_executor_env_scrubs_forged_controls_in_no_skill(tmp_path: Path) -> None:
    """Guards protocol v1 on base aadad44: callers cannot forge adapter policy."""
    task = tmp_path / "task"
    task.mkdir()
    policy = resolve_task_skill_policy(
        task_path=task,
        skill_mode="no-skill",
        runtime_skills_dir=None,
        declared_sandbox_skills_dir=None,
    )

    env = apply_openhands_executor_env(
        "openhands",
        {
            ENV_SKILLS_ROOT: "/forged",
            ENV_MAX_ITERATIONS: "999",
            ENV_LLM_TIMEOUT: "1",
            ENV_DISABLE_SUBAGENTS: "0",
            "SAFE": "yes",
        },
        skill_policy=policy,
        manifest=None,
    )

    assert ENV_SKILLS_ROOT not in env
    assert env[ENV_MAX_ITERATIONS] == "60"
    assert env[ENV_LLM_TIMEOUT] == "3600"
    assert env[ENV_DISABLE_SUBAGENTS] == "1"
    assert env["SAFE"] == "yes"


def test_executor_accepts_selected_model_routes_but_requires_one() -> None:
    """Guards protocol v1 on base aadad44: model selection stays explicit."""
    validate_openhands_executor_model("openhands", "openrouter/openai/gpt-5.2")
    validate_openhands_executor_model("openhands", "openai/gpt-5.2")
    validate_openhands_executor_model("openhands", "deepseek/deepseek-chat")

    with pytest.raises(ValueError, match="explicit model route"):
        validate_openhands_executor_model("openhands", None)
    with pytest.raises(ValueError, match="provider-qualified"):
        validate_openhands_executor_model("openhands", "gpt-5.2")
    with pytest.raises(ValueError, match="provider-qualified"):
        validate_openhands_executor_model("openhands", "unknown/model")

    with pytest.raises(ValueError, match="agent_env overrides"):
        validate_openhands_executor_agent_env(
            "openhands", {"LLM_BASE_URL": "https://alternate.example/v1"}
        )
    validate_openhands_executor_agent_env(
        "openhands", {"OPENROUTER_API_KEY": "placeholder"}
    )

    # Retained upstream agents are not labelled as canonical executor runs.
    validate_openhands_executor_model("gemini", "google/gemini")


def test_version_manifest_matches_runtime_constants() -> None:
    """Guards protocol v1 on base aadad44 against release/runtime pin drift."""
    version_file = Path(__file__).parents[1] / "BENCHMARK_EXECUTOR_VERSION.json"
    version = json.loads(version_file.read_text())

    assert version == protocol_descriptor()
    assert version["protocol_version"] == 1
    assert version["base_commit"] == BENCHFLOW_BASE_COMMIT
    assert version["openhands_cli_commit"] == OPENHANDS_CLI_COMMIT
    assert "model" not in version
    assert version["max_parent_iterations_per_step"] == 60


def test_method_skill_bundle_requires_exactly_one_selected_task() -> None:
    """Guards protocol v1 on base aadad44 against cross-task bundle reuse."""
    validate_method_skill_task_count(None, 25)
    validate_method_skill_task_count("/candidate/full-skills", 1)

    with pytest.raises(ValueError, match="exactly one selected task"):
        validate_method_skill_task_count("/candidate/full-skills", 2)


@pytest.mark.asyncio
async def test_evaluation_rejects_one_custom_bundle_for_multiple_tasks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Guards protocol v1 on base aadad44: Evaluation wires the batch gate."""
    from benchflow.evaluation import Evaluation, EvaluationConfig

    tasks = tmp_path / "tasks"
    tasks.mkdir()
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    evaluation = Evaluation(
        tasks_dir=tasks,
        jobs_dir=tmp_path / "jobs",
        config=EvaluationConfig(
            agent="openhands",
            model="openrouter/openai/gpt-5.2",
            skills_dir=str(candidate),
            skill_mode="with-skill",
        ),
    )
    monkeypatch.setattr(
        evaluation, "_get_task_dirs", lambda: [tasks / "one", tasks / "two"]
    )

    with pytest.raises(ValueError, match="exactly one selected task"):
        await evaluation.run()


def test_canonical_scenes_reject_local_skills_and_mixed_roles() -> None:
    """Guards protocol v1 on base aadad44 against Scene policy bypasses."""
    valid_role = SimpleNamespace(
        agent="openhands",
        model="openrouter/openai/gpt-5.2",
        reasoning_effort="high",
        env={},
        skills_dir=None,
    )
    validate_openhands_executor_scenes(
        [SimpleNamespace(skills_dir=None, roles=[valid_role])],
        expected_model="openrouter/openai/gpt-5.2",
        expected_reasoning_effort="high",
    )

    with pytest.raises(ValueError, match="Scene-local"):
        validate_openhands_executor_scenes(
            [SimpleNamespace(skills_dir="/alternate", roles=[valid_role])],
            expected_model="openrouter/openai/gpt-5.2",
        )
    with pytest.raises(ValueError, match="every Scene role"):
        validate_openhands_executor_scenes(
            [
                SimpleNamespace(
                    skills_dir=None,
                    roles=[
                        SimpleNamespace(
                            agent="gemini", model="google/gemini", skills_dir=None
                        )
                    ],
                )
            ],
            expected_model="openrouter/openai/gpt-5.2",
        )
    with pytest.raises(ValueError, match="selected for this rollout"):
        validate_openhands_executor_scenes(
            [SimpleNamespace(skills_dir=None, roles=[valid_role])],
            expected_model="openai/gpt-5.2",
            expected_reasoning_effort="high",
        )
    with pytest.raises(ValueError, match="reasoning effort"):
        validate_openhands_executor_scenes(
            [SimpleNamespace(skills_dir=None, roles=[valid_role])],
            expected_model="openrouter/openai/gpt-5.2",
            expected_reasoning_effort="low",
        )
    with pytest.raises(ValueError, match="Role-local env"):
        validate_openhands_executor_scenes(
            [
                SimpleNamespace(
                    skills_dir=None,
                    roles=[
                        SimpleNamespace(
                            agent="openhands",
                            model="openrouter/openai/gpt-5.2",
                            reasoning_effort="high",
                            env={"LLM_BASE_URL": "https://alternate.example/v1"},
                            skills_dir=None,
                        )
                    ],
                )
            ],
            expected_model="openrouter/openai/gpt-5.2",
            expected_reasoning_effort="high",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role_agent", "role_model", "role_reasoning", "message"),
    [
        ("gemini", "google/gemini-2.5-pro", "high", "every Scene role"),
        (
            "openhands",
            "deepseek/deepseek-chat",
            "high",
            "selected for this rollout",
        ),
        (
            "openhands",
            "openrouter/openai/gpt-5.2",
            "low",
            "reasoning effort",
        ),
    ],
)
async def test_task_document_cannot_override_executor_selection(
    tmp_path: Path,
    role_agent: str,
    role_model: str,
    role_reasoning: str,
    message: str,
) -> None:
    """Guards protocol v1: task Scenes cannot replace caller model policy."""
    from benchflow.rollout import Rollout, RolloutConfig

    task = tmp_path / "task"
    task.mkdir()
    (task / "task.md").write_text(
        f"""---
agents:
  roles:
    solver:
      agent: {role_agent}
      model: {role_model}
      reasoning_effort: {role_reasoning}
scenes:
  - name: solve
    roles: [solver]
---
## prompt

Solve the task.
"""
    )
    config = RolloutConfig.from_legacy(
        task_path=task,
        agent="openhands",
        model="openrouter/openai/gpt-5.2",
        reasoning_effort="high",
        jobs_dir=tmp_path / "jobs",
    )

    with pytest.raises(ValueError, match=message):
        await Rollout(config).setup()
    assert not (tmp_path / "jobs").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("network_mode", ["public", "no-network"])
async def test_verifier_proxy_overlay_stays_out_of_agent_and_task_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    network_mode: str,
) -> None:
    """Guards this proxy change: verifier env never relaxes the task network."""

    from benchflow.rollout import Rollout, RolloutConfig

    monkeypatch.setenv("OPENROUTER_API_KEY", "placeholder-key")
    task = tmp_path / "task"
    (task / "environment").mkdir(parents=True)
    (task / "verifier").mkdir()
    (task / "environment" / "Dockerfile").write_text("FROM ubuntu:24.04\n")
    (task / "verifier" / "test.sh").write_text("#!/bin/sh\nexit 0\n")
    (task / "task.md").write_text(
        f"""---
verifier:
  type: test-script
  env:
    EXISTING_VERIFIER_VAR: preserved
environment:
  network_mode: {network_mode}
---
Solve the task.
"""
    )
    endpoint = "http://host.docker.internal:18080"
    config = RolloutConfig.from_legacy(
        task_path=task,
        agent="openhands",
        model="openrouter/openai/gpt-5.2",
        jobs_dir=tmp_path / "jobs",
        job_name="proxy-isolation",
        rollout_name="run-1",
        verifier_env_overlay={
            "HTTP_PROXY": endpoint,
            "http_proxy": endpoint,
        },
        verifier_proxy_metadata={
            "mode": "explicit",
            "enabled": True,
            "scope": "verifier-process-only",
        },
    )
    rollout = Rollout(config)

    await rollout.setup()

    assert rollout._task.config.verifier.env["EXISTING_VERIFIER_VAR"] == "preserved"
    assert "HTTP_PROXY" not in rollout._task.config.verifier.env
    assert rollout._config.verifier_env_overlay["HTTP_PROXY"] == endpoint
    assert "HTTP_PROXY" not in rollout._agent_env
    assert "http_proxy" not in rollout._agent_env
    assert "HTTP_PROXY" not in (rollout._task.config.environment.env or {})
    assert rollout._task.config.environment.network_mode.value == network_mode
    config_text = (rollout._rollout_dir / "config.json").read_text()
    assert endpoint not in config_text
    assert '"mode": "explicit"' in config_text


def test_executor_records_original_skill_preload_metadata(tmp_path: Path) -> None:
    """Guards protocol v1 on base aadad44: original Skill preload is auditable."""
    task = tmp_path / "task"
    skills = _bundle(task / "environment")
    policy = resolve_task_skill_policy(
        task_path=task,
        skill_mode="with-skill",
        runtime_skills_dir=None,
        declared_sandbox_skills_dir="/skills",
    )
    manifest = build_skill_bundle_manifest(skills)

    env = apply_openhands_executor_env(
        "openhands", {}, skill_policy=policy, manifest=manifest
    )
    metadata = executor_metadata(
        agent="openhands",
        model="openrouter/openai/gpt-5.2",
        skill_policy=policy,
        manifest=manifest,
    )

    assert env[ENV_SKILLS_ROOT] == "/skills"
    assert metadata is not None
    assert metadata["evaluation_condition"] == "original-skill"
    assert metadata["skill_context_preloaded"] is True
    assert metadata["preloaded_skill_count"] == 2
    assert metadata["model"] == "openrouter/openai/gpt-5.2"
    assert metadata["benchflow_base_commit"] == (
        "aadad44acf27f193df98f438443116d514f51fb8"
    )


def test_executor_labels_all_three_conditions(tmp_path: Path) -> None:
    """Guards protocol v1 on base aadad44: condition labels stay comparable."""
    task = tmp_path / "task"
    bundled = _bundle(task / "environment")
    custom = _bundle(tmp_path / "candidate")
    cases = [
        ("no-skill", None, "no-skill"),
        ("with-skill", None, "original-skill"),
        ("with-skill", custom, "method-skill"),
    ]

    for mode, runtime_dir, expected in cases:
        policy = resolve_task_skill_policy(
            task_path=task,
            skill_mode=mode,
            runtime_skills_dir=runtime_dir,
            declared_sandbox_skills_dir="/skills",
        )
        root = policy.host_dir
        manifest = build_skill_bundle_manifest(root) if root is not None else None
        metadata = executor_metadata(
            agent="openhands",
            model="deepseek/deepseek-chat",
            skill_policy=policy,
            manifest=manifest,
            resolved_agent_env={
                "BENCHFLOW_PROVIDER_NAME": "deepseek",
                "BENCHFLOW_PROVIDER_BASE_URL": "https://api.deepseek.com/v1",
                "BENCHFLOW_PROVIDER_PROTOCOL": "openai-completions",
            },
        )

        assert metadata is not None
        assert metadata["evaluation_condition"] == expected
        assert metadata["skill_context_preloaded"] is (expected != "no-skill")
        assert metadata["model"] == "deepseek/deepseek-chat"
        assert metadata["provider_route"] == "deepseek"
        assert metadata["provider_base_url"] == "https://api.deepseek.com/v1"
        assert metadata["provider_protocol"] == "openai-completions"

    assert bundled.is_dir()

    with pytest.raises(RuntimeError, match="resolved provider"):
        executor_metadata(
            agent="openhands",
            model="deepseek/deepseek-chat",
            skill_policy=policy,
            manifest=manifest,
            resolved_agent_env={"BENCHFLOW_PROVIDER_NAME": "openrouter"},
        )


def test_config_and_result_artifacts_persist_executor_evidence(tmp_path: Path) -> None:
    """Guards protocol v1 on base aadad44: persisted evidence closes the loop."""
    from benchflow.rollout import _build_rollout_result, _write_config

    task = tmp_path / "task"
    skills = _bundle(task / "environment")
    policy = resolve_task_skill_policy(
        task_path=task,
        skill_mode="with-skill",
        runtime_skills_dir=None,
        declared_sandbox_skills_dir="/skills",
    )
    manifest = build_skill_bundle_manifest(skills)
    metadata = executor_metadata(
        agent="openhands",
        model="openrouter/openai/gpt-5.2",
        skill_policy=policy,
        manifest=manifest,
    )
    assert metadata is not None
    rollout_dir = tmp_path / "rollout"
    rollout_dir.mkdir()
    started = datetime.now()

    _write_config(
        rollout_dir,
        task_path=task,
        agent="openhands",
        model="openrouter/openai/gpt-5.2",
        environment="docker",
        skill_policy=policy,
        sandbox_user="agent",
        context_root=None,
        timeout=21_600,
        started_at=started,
        agent_env={},
        executor_metadata=metadata,
    )
    outcome = {
        "type": "agent_iteration_outcome",
        "prompt_ordinal": 1,
        "stop_reason": "end_turn",
        "acp_stop_reason": "end_turn",
        "execution_status": "finished",
        "error_code": None,
        "iterations_used": 23,
        "max_iterations": 60,
        "skill_context_preloaded": True,
        "skill_bundle_sha256": f"sha256:{manifest.sha256}",
        "preloaded_skill_count": manifest.skill_count,
    }
    _build_rollout_result(
        rollout_dir,
        task_name=task.name,
        rollout_name="run-1",
        agent="openhands",
        agent_name="openhands",
        model="openrouter/openai/gpt-5.2",
        n_tool_calls=1,
        prompts=["solve"],
        error=None,
        verifier_error=None,
        trajectory=[{"type": "user_message", "text": "solve"}, outcome],
        partial_trajectory=False,
        rewards={"reward": 1.0},
        started_at=started,
        timing={"agent": 1.0},
        skill_policy=policy,
        executor_metadata=metadata,
    )

    config = json.loads((rollout_dir / "config.json").read_text())
    result = json.loads((rollout_dir / "result.json").read_text())
    assert config["executor"]["protocol_version"] == 1
    assert config["executor"]["skill_bundle_sha256"] == f"sha256:{manifest.sha256}"
    assert result["executor"]["skill_context_preload_observed"] is True
    assert result["executor"]["skill_context_preload_matches_expected"] is True
    assert result["agent_result"]["iterations_used"] == 23
    assert result["agent_result"]["stop_reason"] == "end_turn"

    failed_dir = tmp_path / "failed-rollout"
    _build_rollout_result(
        failed_dir,
        task_name=task.name,
        rollout_name="run-2",
        agent="openhands",
        agent_name="openhands",
        model="openrouter/openai/gpt-5.2",
        n_tool_calls=1,
        prompts=["step one", "step two"],
        error="ACP prompt failed",
        verifier_error=None,
        trajectory=[
            {"type": "user_message", "text": "step one"},
            outcome,
            {"type": "user_message", "text": "step two"},
        ],
        partial_trajectory=True,
        rewards=None,
        started_at=started,
        timing={"agent": 1.0},
        skill_policy=policy,
        executor_metadata=metadata,
    )
    failed = json.loads((failed_dir / "result.json").read_text())
    assert failed["agent_result"]["stop_reason"] == "conversation_error"
    assert failed["executor"]["iteration_accounting_complete"] is False


def test_result_metadata_distinguishes_iteration_limit_from_infra_error() -> None:
    """Guards protocol v1 on base aadad44: N=60 is not an infra failure."""
    observed = executor_result_metadata(
        {"max_parent_iterations_per_step": 60},
        [
            {
                "type": "agent_iteration_outcome",
                "prompt_ordinal": 1,
                "stop_reason": "max_iterations",
                "acp_stop_reason": "max_turn_requests",
                "execution_status": None,
                "error_code": None,
                "iterations_used": 60,
                "max_iterations": 60,
                "skill_context_preloaded": True,
                "skill_bundle_sha256": "sha256:" + "a" * 64,
                "preloaded_skill_count": 2,
            }
        ],
    )

    assert observed is not None
    assert observed["iteration_limit_reached"] is True
    assert observed["stop_reason"] == "max_iterations"
    assert observed["prompt_runs"] == [
        {
            "prompt_ordinal": 1,
            "stop_reason": "max_iterations",
            "acp_stop_reason": "max_turn_requests",
            "execution_status": None,
            "error_code": None,
            "iterations_used": 60,
            "max_iterations": 60,
            "skill_context_preloaded": True,
            "skill_bundle_sha256": "sha256:" + "a" * 64,
            "preloaded_skill_count": 2,
        }
    ]


@pytest.mark.asyncio
async def test_acp_records_namespaced_iteration_outcome_without_extra_prompt() -> None:
    """Guards protocol v1 on base aadad44: metadata adds no synthetic turn."""

    class Client:
        async def prompt(self, prompt: str) -> SimpleNamespace:
            assert prompt == "original task"
            return SimpleNamespace(
                stop_reason="end_turn",
                field_meta={
                    "benchmark_executor": {
                        "stop_reason": "end_turn",
                        "acp_stop_reason": "end_turn",
                        "iterations_used": 7,
                        "max_iterations": 60,
                        "skill_context_preloaded": False,
                        "skill_bundle_sha256": None,
                        "preloaded_skill_count": 0,
                    }
                },
            )

    session = ACPSession("session")
    trajectory, _ = await execute_prompts(
        Client(), session, ["original task"], timeout=5, idle_timeout=None
    )

    outcomes = [
        event for event in trajectory if event["type"] == "agent_iteration_outcome"
    ]
    assert len(outcomes) == 1
    assert outcomes[0]["iterations_used"] == 7
    assert outcomes[0]["max_iterations"] == MAX_PARENT_ITERATIONS_PER_STEP
    assert [event for event in trajectory if event["type"] == "user_message"] == [
        {"type": "user_message", "text": "original task"}
    ]
