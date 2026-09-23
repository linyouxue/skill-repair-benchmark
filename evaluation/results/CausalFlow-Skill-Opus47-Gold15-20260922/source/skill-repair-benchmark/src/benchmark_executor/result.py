"""Normalized result contract for repair algorithms using the executor."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from benchflow.benchmark_executor import (
    BENCHFLOW_BASE_COMMIT,
    EXECUTOR_AGENT,
    EXECUTOR_PROTOCOL_VERSION,
    EXECUTOR_SANDBOX,
    EXECUTOR_SKILL_EXPOSURE_MODE,
    MAX_PARENT_ITERATIONS_PER_STEP,
    provider_route_for_model,
)


class BenchmarkResultError(RuntimeError):
    """A completed rollout has a missing or malformed result artifact."""


@dataclass(frozen=True, slots=True)
class BenchmarkArtifacts:
    """Stable rollout paths; ``task_artifacts_dir`` may legitimately be empty."""

    rollout_dir: Path
    result_json: Path
    request_json: Path
    config_json: Path | None
    acp_trajectory_jsonl: Path | None
    llm_trajectory_jsonl: Path | None
    verifier_dir: Path
    task_artifacts_dir: Path


@dataclass(frozen=True, slots=True)
class SkillExposure:
    """Expected and sandbox-observed persistent AgentContext exposure."""

    condition: str | None
    expected: bool | None
    observed: bool | None
    verified: bool | None
    expected_bundle_sha256: str | None
    observed_bundle_sha256: str | None
    expected_skill_count: int | None
    observed_skill_count: int | None
    native_skill_invocations: int


def _json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BenchmarkResultError(f"cannot read JSON object {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise BenchmarkResultError(f"expected a JSON object: {path}")
    return value


def _optional_json_object(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return _json_object(path)
    except BenchmarkResultError:
        return None


def _strict_jsonl(path: Path) -> tuple[dict[str, Any], ...]:
    records: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise BenchmarkResultError(f"cannot read JSONL {path}: {exc}") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BenchmarkResultError(
                f"invalid JSONL {path} line {line_number}: {exc}"
            ) from exc
        if not isinstance(record, dict):
            raise BenchmarkResultError(
                f"invalid JSONL {path} line {line_number}: expected object"
            )
        records.append(record)
    return tuple(records)


def _finite_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _optional_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _same_or_none(values: list[Any]) -> Any:
    if not values:
        return None
    first = values[0]
    return first if all(value == first for value in values) else None


def _skill_exposure(raw: dict[str, Any]) -> SkillExposure:
    executor = raw.get("executor")
    executor = executor if isinstance(executor, dict) else {}
    prompt_runs = executor.get("prompt_runs")
    runs = [run for run in prompt_runs or [] if isinstance(run, dict)]
    expected = executor.get("skill_context_preloaded")
    expected = expected if isinstance(expected, bool) else None
    expected_sha = executor.get("skill_bundle_sha256")
    expected_sha = expected_sha if isinstance(expected_sha, str) else None
    expected_count = _optional_int(executor.get("preloaded_skill_count"))

    observed_values = [run.get("skill_context_preloaded") for run in runs]
    observed_shas = [run.get("skill_bundle_sha256") for run in runs]
    observed_counts = [run.get("preloaded_skill_count") for run in runs]
    observed = _same_or_none(observed_values)
    observed = observed if isinstance(observed, bool) else None
    observed_sha = _same_or_none(observed_shas)
    observed_sha = observed_sha if isinstance(observed_sha, str) else None
    observed_count = _optional_int(_same_or_none(observed_counts))

    verified: bool | None = None
    if runs and expected is not None:
        if expected:
            verified = all(
                run.get("skill_context_preloaded") is True
                and run.get("skill_bundle_sha256") == expected_sha
                and _optional_int(run.get("preloaded_skill_count")) == expected_count
                for run in runs
            )
        else:
            verified = all(
                run.get("skill_context_preloaded") is False
                and run.get("skill_bundle_sha256") is None
                and _optional_int(run.get("preloaded_skill_count")) == 0
                for run in runs
            )

    return SkillExposure(
        condition=(
            str(executor["evaluation_condition"])
            if executor.get("evaluation_condition") is not None
            else None
        ),
        expected=expected,
        observed=observed,
        verified=verified,
        expected_bundle_sha256=expected_sha,
        observed_bundle_sha256=observed_sha,
        expected_skill_count=expected_count,
        observed_skill_count=observed_count,
        native_skill_invocations=_optional_int(raw.get("n_skill_invocations")) or 0,
    )


def _protocol_evidence_valid(
    raw: dict[str, Any],
    config: dict[str, Any] | None,
    *,
    protocol_id: str,
    expected_model: str,
    expected_reasoning_effort: str | None,
) -> bool:
    executor = raw.get("executor")
    if not isinstance(executor, dict) or config is None:
        return False
    config_executor = config.get("executor")
    if not isinstance(config_executor, dict):
        return False
    expected_provider = provider_route_for_model(expected_model)
    return all(
        (
            executor.get("protocol_id") == protocol_id,
            executor.get("protocol_version") == EXECUTOR_PROTOCOL_VERSION,
            executor.get("benchflow_base_commit") == BENCHFLOW_BASE_COMMIT,
            executor.get("agent") == EXECUTOR_AGENT,
            executor.get("model") == expected_model,
            executor.get("provider_route") == expected_provider,
            isinstance(executor.get("provider_base_url"), str),
            isinstance(executor.get("provider_protocol"), str),
            executor.get("skill_exposure_mode") == EXECUTOR_SKILL_EXPOSURE_MODE,
            executor.get("max_parent_iterations_per_step")
            == MAX_PARENT_ITERATIONS_PER_STEP,
            raw.get("agent") == EXECUTOR_AGENT,
            raw.get("model") == expected_model,
            config.get("agent") == EXECUTOR_AGENT,
            config.get("model") == expected_model,
            config_executor.get("model") == expected_model,
            config_executor.get("provider_route") == expected_provider,
            config_executor.get("provider_base_url")
            == executor.get("provider_base_url"),
            config_executor.get("provider_protocol")
            == executor.get("provider_protocol"),
            config.get("environment") == EXECUTOR_SANDBOX,
            config.get("reasoning_effort") == expected_reasoning_effort,
            isinstance(config.get("task_digest"), str),
        )
    )


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    """One task rollout normalized for diagnosis and repair algorithms."""

    task_id: str
    rollout_id: str
    method_id: str
    stage: str
    protocol_id: str
    model: str
    provider_route: str
    provider_base_url: str | None
    provider_protocol: str | None
    reasoning_effort: str | None
    reward: float | None
    verifier_components: dict[str, Any] | None
    trajectory: tuple[dict[str, Any], ...]
    trajectory_complete: bool
    artifacts: BenchmarkArtifacts
    agent_iterations: int | None
    iteration_accounting_complete: bool
    provider_requests: int | None
    skill_exposure: SkillExposure
    wall_time_sec: float | None
    cost_usd: float | None
    termination_reason: str | None
    error: str | None
    error_category: str | None
    verifier_error: str | None
    verifier_error_category: str | None
    export_error: str | None
    protocol_evidence_valid: bool
    raw_result: dict[str, Any]

    @property
    def execution_ok(self) -> bool:
        """Whether the agent, verifier, and export paths completed cleanly."""

        return not (self.error or self.verifier_error or self.export_error)

    @property
    def task_passed(self) -> bool | None:
        """Official task verdict; ``None`` means no trustworthy verdict exists."""

        if not self.execution_ok or self.reward is None:
            return None
        return self.reward == 1.0

    @property
    def success(self) -> bool | None:
        """Convenience alias for :attr:`task_passed`, not execution health."""

        return self.task_passed

    @property
    def comparable(self) -> bool:
        """Whether this result has complete evidence for method comparison."""

        return bool(
            self.protocol_evidence_valid
            and self.execution_ok
            and self.reward is not None
            and self.trajectory_complete
            and self.iteration_accounting_complete
            and self.skill_exposure.verified is True
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a compact JSON-serializable summary without copying trajectory."""

        return {
            "task_id": self.task_id,
            "rollout_id": self.rollout_id,
            "method_id": self.method_id,
            "stage": self.stage,
            "protocol_id": self.protocol_id,
            "model": self.model,
            "provider_route": self.provider_route,
            "provider_base_url": self.provider_base_url,
            "provider_protocol": self.provider_protocol,
            "reasoning_effort": self.reasoning_effort,
            "task_passed": self.task_passed,
            "execution_ok": self.execution_ok,
            "comparable": self.comparable,
            "reward": self.reward,
            "agent_iterations": self.agent_iterations,
            "provider_requests": self.provider_requests,
            "wall_time_sec": self.wall_time_sec,
            "cost_usd": self.cost_usd,
            "termination_reason": self.termination_reason,
            "error": self.error,
            "error_category": self.error_category,
            "verifier_error": self.verifier_error,
            "verifier_error_category": self.verifier_error_category,
            "export_error": self.export_error,
            "protocol_evidence_valid": self.protocol_evidence_valid,
            "trajectory_complete": self.trajectory_complete,
            "iteration_accounting_complete": self.iteration_accounting_complete,
            "skill_exposure_verified": self.skill_exposure.verified,
            "rollout_dir": str(self.artifacts.rollout_dir),
            "result_json": str(self.artifacts.result_json),
        }

    @classmethod
    def from_result_json(
        cls,
        result_json: Path,
        *,
        request_json: Path,
        task_id: str,
        rollout_id: str,
        method_id: str,
        stage: str,
        protocol_id: str,
        expected_model: str,
        expected_reasoning_effort: str | None,
    ) -> BenchmarkResult:
        """Load one canonical persisted result without inventing missing metrics."""

        raw = _json_object(result_json)
        rollout_dir = result_json.parent
        config_path = rollout_dir / "config.json"
        config = _optional_json_object(config_path)
        acp_path = rollout_dir / "trajectory" / "acp_trajectory.jsonl"
        trajectory_valid = acp_path.is_file()
        if trajectory_valid:
            try:
                trajectory = _strict_jsonl(acp_path)
            except BenchmarkResultError:
                trajectory = ()
                trajectory_valid = False
        else:
            trajectory = ()

        llm_path = rollout_dir / "trajectory" / "llm_trajectory.jsonl"
        provider_requests: int | None = None
        if llm_path.is_file():
            try:
                provider_requests = len(_strict_jsonl(llm_path))
            except BenchmarkResultError:
                provider_requests = None

        rewards = raw.get("rewards")
        rewards = rewards if isinstance(rewards, dict) else None
        reward = _finite_float(rewards.get("reward") if rewards else None)
        components = (
            {key: value for key, value in rewards.items() if key != "reward"}
            if rewards is not None
            else None
        )
        agent_result = raw.get("agent_result")
        agent_result = agent_result if isinstance(agent_result, dict) else {}
        executor = raw.get("executor")
        executor = executor if isinstance(executor, dict) else {}
        timing = raw.get("timing")
        timing = timing if isinstance(timing, dict) else {}
        exposure = _skill_exposure(raw)

        artifacts = BenchmarkArtifacts(
            rollout_dir=rollout_dir,
            result_json=result_json,
            request_json=request_json,
            config_json=config_path if config_path.is_file() else None,
            acp_trajectory_jsonl=acp_path if acp_path.is_file() else None,
            llm_trajectory_jsonl=llm_path if llm_path.is_file() else None,
            verifier_dir=rollout_dir / "verifier",
            task_artifacts_dir=rollout_dir / "artifacts",
        )
        return cls(
            task_id=task_id,
            rollout_id=rollout_id,
            method_id=method_id,
            stage=stage,
            protocol_id=protocol_id,
            model=expected_model,
            provider_route=provider_route_for_model(expected_model),
            provider_base_url=(
                executor["provider_base_url"]
                if isinstance(executor.get("provider_base_url"), str)
                else None
            ),
            provider_protocol=(
                executor["provider_protocol"]
                if isinstance(executor.get("provider_protocol"), str)
                else None
            ),
            reasoning_effort=expected_reasoning_effort,
            reward=reward,
            verifier_components=components,
            trajectory=trajectory,
            trajectory_complete=trajectory_valid
            and not bool(raw.get("partial_trajectory")),
            artifacts=artifacts,
            agent_iterations=_optional_int(agent_result.get("iterations_used")),
            iteration_accounting_complete=(
                executor.get("iteration_accounting_complete") is True
            ),
            provider_requests=provider_requests,
            skill_exposure=exposure,
            wall_time_sec=_finite_float(timing.get("total")),
            cost_usd=_finite_float(agent_result.get("cost_usd")),
            termination_reason=(
                str(agent_result["stop_reason"])
                if agent_result.get("stop_reason") is not None
                else None
            ),
            error=str(raw["error"]) if raw.get("error") is not None else None,
            error_category=(
                str(raw["error_category"])
                if raw.get("error_category") is not None
                else None
            ),
            verifier_error=(
                str(raw["verifier_error"])
                if raw.get("verifier_error") is not None
                else None
            ),
            verifier_error_category=(
                str(raw["verifier_error_category"])
                if raw.get("verifier_error_category") is not None
                else None
            ),
            export_error=(
                str(raw["export_error"])
                if raw.get("export_error") is not None
                else None
            ),
            protocol_evidence_valid=_protocol_evidence_valid(
                raw,
                config,
                protocol_id=protocol_id,
                expected_model=expected_model,
                expected_reasoning_effort=expected_reasoning_effort,
            ),
            raw_result=raw,
        )
