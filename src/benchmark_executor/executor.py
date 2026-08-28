"""Programmatic single-rollout entry point shared by repair algorithms."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import benchflow as bf
from benchflow._utils.benchmark_repos import task_source_provenance
from benchflow._utils.config import normalize_reasoning_effort
from benchflow._utils.hf_datasets import load_source_sidecar
from benchflow._utils.task_authoring import task_digest
from benchflow.benchmark_executor import (
    EXECUTOR_AGENT,
    EXECUTOR_PROTOCOL_ID,
    EXECUTOR_SANDBOX,
    EXECUTOR_USAGE_TRACKING,
    IDLE_SAFETY_TIMEOUT_SEC,
    build_skill_bundle_manifest,
    protocol_descriptor,
    provider_route_for_model,
)
from benchflow.evaluation import _environment_manifest_from_task_document
from benchflow.rollout import RolloutConfig
from benchflow.skill_policy import SKILL_MODE_NO_SKILL, SKILL_MODE_WITH_SKILL
from benchflow.usage_tracking import UsageTrackingConfig
from benchmark_executor.result import BenchmarkResult

EvaluationCondition = Literal["no-skill", "original-skill", "method-skill"]
_CONDITIONS = frozenset({"no-skill", "original-skill", "method-skill"})


class BenchmarkExecutionError(RuntimeError):
    """The executor could not produce a canonical persisted rollout result."""


def _path_component(value: str, *, field: str) -> str:
    value = value.strip()
    if (
        not value
        or len(value) > 128
        or value in {".", ".."}
        or "/" in value
        or "\\" in value
        or any(ord(char) < 32 for char in value)
    ):
        raise ValueError(f"{field} must be one safe path component")
    return value


def _label(value: str, *, field: str) -> str:
    value = value.strip()
    if not value or len(value) > 256 or any(ord(char) < 32 for char in value):
        raise ValueError(f"{field} must be a non-empty label")
    return value


class BenchmarkExecutor:
    """Execute one task under a fixed harness protocol and selected model route.

    The model/provider route and reasoning effort are selected once when this
    object is constructed.  Individual repair rounds cannot override them.
    """

    def __init__(
        self,
        *,
        tasks_root: str | Path,
        jobs_root: str | Path,
        model: str,
        reasoning_effort: str | None = None,
        protocol: str = EXECUTOR_PROTOCOL_ID,
    ) -> None:
        if protocol != EXECUTOR_PROTOCOL_ID:
            raise ValueError(
                f"unsupported executor protocol {protocol!r}; "
                f"expected {EXECUTOR_PROTOCOL_ID!r}"
            )
        model = model.strip()
        if not model:
            raise ValueError("model must be an explicit BenchFlow/LiteLLM route")
        root = Path(tasks_root).expanduser().resolve(strict=True)
        if not root.is_dir():
            raise ValueError(f"tasks_root is not a directory: {root}")
        self.tasks_root = root
        self.jobs_root = Path(jobs_root).expanduser().resolve()
        self.model = model
        self.provider_route = provider_route_for_model(model)
        self.reasoning_effort = normalize_reasoning_effort(reasoning_effort)
        self.protocol = protocol

    def _task_path(self, task_id: str) -> Path:
        task_id = _path_component(task_id, field="task_id")
        if self.tasks_root.name == task_id:
            candidate = self.tasks_root
        else:
            candidate = self.tasks_root / task_id
        candidate = candidate.resolve(strict=True)
        if not candidate.is_dir() or (
            candidate != self.tasks_root
            and not candidate.is_relative_to(self.tasks_root)
        ):
            raise ValueError(f"task_id does not resolve inside tasks_root: {task_id}")
        return candidate

    @staticmethod
    def _condition_inputs(
        condition: EvaluationCondition,
        skill_bundle: str | Path | None,
    ) -> tuple[str, Path | None, dict | None]:
        if condition not in _CONDITIONS:
            raise ValueError(f"unknown evaluation condition: {condition!r}")
        if condition == "method-skill":
            if skill_bundle is None:
                raise ValueError("method-skill requires a complete skill_bundle")
            bundle = Path(skill_bundle).expanduser().resolve(strict=True)
            manifest = build_skill_bundle_manifest(bundle)
            return SKILL_MODE_WITH_SKILL, bundle, manifest.to_metadata()
        if skill_bundle is not None:
            raise ValueError(f"{condition} does not accept skill_bundle")
        if condition == "original-skill":
            return SKILL_MODE_WITH_SKILL, None, None
        return SKILL_MODE_NO_SKILL, None, None

    def _request_payload(
        self,
        *,
        task_id: str,
        task_digest_value: str,
        condition: EvaluationCondition,
        bundle: Path | None,
        bundle_metadata: dict | None,
        method_id: str,
        stage: str,
        rollout_id: str,
    ) -> dict:
        return {
            "schema_version": 1,
            "created_at": datetime.now(UTC).isoformat(),
            "protocol": protocol_descriptor(),
            "model_selection": {
                "model": self.model,
                "provider_route": self.provider_route,
                "reasoning_effort": self.reasoning_effort,
            },
            "task_id": task_id,
            "task_digest": task_digest_value,
            "condition": condition,
            "method_id": method_id,
            "stage": stage,
            "rollout_id": rollout_id,
            "skill_bundle": str(bundle) if bundle is not None else None,
            "skill_bundle_manifest": bundle_metadata,
        }

    async def run_async(
        self,
        *,
        task_id: str,
        method_id: str,
        stage: str,
        rollout_id: str,
        condition: EvaluationCondition = "method-skill",
        skill_bundle: str | Path | None = None,
    ) -> BenchmarkResult:
        """Run exactly one task rollout through the shared BenchFlow backend."""

        task_id = _path_component(task_id, field="task_id")
        method_id = _path_component(method_id, field="method_id")
        rollout_id = _path_component(rollout_id, field="rollout_id")
        stage = _label(stage, field="stage")
        task_path = self._task_path(task_id)
        skill_mode, bundle, bundle_metadata = self._condition_inputs(
            condition, skill_bundle
        )
        task_digest_value = task_digest(task_path)

        job_dir = self.jobs_root / method_id
        job_dir.mkdir(parents=True, exist_ok=True)
        rollout_dir = job_dir / rollout_id
        rollout_dir.mkdir(exist_ok=False)
        request_json = rollout_dir / "executor_request.json"
        request_json.write_text(
            json.dumps(
                self._request_payload(
                    task_id=task_id,
                    task_digest_value=task_digest_value,
                    condition=condition,
                    bundle=bundle,
                    bundle_metadata=bundle_metadata,
                    method_id=method_id,
                    stage=stage,
                    rollout_id=rollout_id,
                ),
                indent=2,
            ),
            encoding="utf-8",
        )

        source = task_source_provenance(load_source_sidecar(self.tasks_root), task_path)
        config = RolloutConfig.from_legacy(
            task_path=task_path,
            agent=EXECUTOR_AGENT,
            model=self.model,
            reasoning_effort=self.reasoning_effort,
            prompts=None,
            environment=EXECUTOR_SANDBOX,
            environment_manifest=_environment_manifest_from_task_document(task_path),
            concurrency=1,
            sandbox_user="agent",
            skip_agent_install=False,
            agent_idle_timeout=IDLE_SAFETY_TIMEOUT_SEC,
            usage_tracking=UsageTrackingConfig(mode=EXECUTOR_USAGE_TRACKING),
            skills_dir=bundle,
            skill_mode=skill_mode,
            job_name=method_id,
            rollout_name=rollout_id,
            jobs_dir=self.jobs_root,
            source_provenance=source,
            task_digest=task_digest_value,
        )
        result_json = rollout_dir / "result.json"
        try:
            await bf.run(config)
        except Exception as exc:
            # BenchFlow persists terminal rollout state before some late export
            # errors are re-raised.  Prefer that canonical evidence when it is
            # available; only fail the API call when no result was persisted.
            if not result_json.is_file():
                raise BenchmarkExecutionError(
                    f"rollout {method_id}/{rollout_id} failed before a canonical "
                    f"result could be returned; inspect {rollout_dir}"
                ) from exc

        if not result_json.is_file():
            raise BenchmarkExecutionError(
                f"rollout returned without result.json: {rollout_dir}"
            )
        result = BenchmarkResult.from_result_json(
            result_json,
            request_json=request_json,
            task_id=task_id,
            rollout_id=rollout_id,
            method_id=method_id,
            stage=stage,
            protocol_id=self.protocol,
            expected_model=self.model,
            expected_reasoning_effort=self.reasoning_effort,
        )
        (rollout_dir / "benchmark_result.json").write_text(
            json.dumps(result.to_dict(), indent=2), encoding="utf-8"
        )
        return result

    def run(
        self,
        *,
        task_id: str,
        method_id: str,
        stage: str,
        rollout_id: str,
        condition: EvaluationCondition = "method-skill",
        skill_bundle: str | Path | None = None,
    ) -> BenchmarkResult:
        """Synchronous wrapper; async programs must use :meth:`run_async`."""

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self.run_async(
                    task_id=task_id,
                    method_id=method_id,
                    stage=stage,
                    rollout_id=rollout_id,
                    condition=condition,
                    skill_bundle=skill_bundle,
                )
            )
        raise RuntimeError(
            "BenchmarkExecutor.run() cannot be called inside a running event "
            "loop; use `await executor.run_async(...)`"
        )
