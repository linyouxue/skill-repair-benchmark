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
from benchflow.task import Task
from benchflow.task.verifier_document import load_verifier_document
from benchflow.usage_tracking import UsageTrackingConfig
from benchmark_executor.result import BenchmarkResult
from benchmark_executor.verifier_proxy import (
    VerifierProxyPreflight,
    VerifierProxySettings,
    resolve_verifier_proxy_settings,
)

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
        verifier_proxy_mode: str | None = None,
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
        # Resolve once per executor instance so every rollout uses the same
        # infrastructure setting. The default is always off, even if the runner
        # itself has HTTP_PROXY/HTTPS_PROXY configured for the model provider.
        self.verifier_proxy: VerifierProxySettings = resolve_verifier_proxy_settings(
            mode=verifier_proxy_mode
        )

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
            # Safe metadata only: proxy URLs, ports, userinfo, and credentials
            # never enter executor_request.json.
            "verifier_proxy": dict(self.verifier_proxy.metadata),
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
        verifier_service = "main"
        if self.verifier_proxy.enabled:
            task = Task(task_path)
            verifier_document = load_verifier_document(task.paths.tests_dir)
            effective_verifier_type = (
                verifier_document.selected_strategy.type
                if verifier_document is not None
                else task.config.verifier.type
            )
            if effective_verifier_type not in {"test-script", "script"}:
                raise ValueError(
                    "verifier proxy is supported only for sandbox test-script "
                    "verifiers; it is never forwarded to host-side verifier judges"
                )
            verifier_service = task.config.verifier.service

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
            verifier_env_overlay=(
                dict(self.verifier_proxy.env) if self.verifier_proxy.enabled else None
            ),
            verifier_proxy_metadata=dict(self.verifier_proxy.metadata),
            pre_agent_hooks=(
                [
                    VerifierProxyPreflight(
                        self.verifier_proxy.endpoints,
                        service=verifier_service,
                    )
                ]
                if self.verifier_proxy.enabled
                else None
            ),
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
