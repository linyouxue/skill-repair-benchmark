"""Adapter from SkillRevise's method loop to the shared benchmark executor.

The shared executor owns *all* real task execution.  SkillRevise keeps the
authoring, diagnosis and revision policy, while this module converts a local
``Skill`` into the executor's immutable full-skill bundle and normalizes the
result back into an ``ExecutionTrace``.

``benchmark_executor`` is deliberately imported lazily.  The normal Windows
development environment can still run the existing local harness and tests;
the unified path is intended for the WSL/Linux environment where the shared
executor package is installed.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol
from uuid import uuid4

from skillrevise.core.agents import AgentAdapter
from skillrevise.core.models import ExecutionTrace, Skill, TaskSpec, TrajectoryEvent


class _ExecutorProtocol(Protocol):
    def run(
        self,
        *,
        task_id: str,
        method_id: str,
        stage: str,
        rollout_id: str,
        condition: str = "method-skill",
        skill_bundle: str | Path | None = None,
    ) -> Any:
        """Run one shared benchmark rollout."""


def build_shared_executor(
    *,
    tasks_root: str | Path,
    jobs_root: str | Path,
    model: str,
    reasoning_effort: str | None = None,
    verifier_proxy_mode: str | None = None,
    text_only_retry_limit: int | None = None,
    prebuilt_images_manifest: str | Path | None = None,
) -> _ExecutorProtocol:
    """Create the public executor without making it a package dependency.

    The shared repository intentionally owns the pinned BenchFlow/OpenHands
    dependency graph.  Installing it in the WSL experiment environment makes
    this import available; local-only SkillRevise users receive an actionable
    error instead of a vague import failure.
    """

    try:
        from benchmark_executor import BenchmarkExecutor
    except ImportError as exc:  # pragma: no cover - depends on external repo
        raise RuntimeError(
            "Unified benchmark execution requires the shared "
            "skill-repair-benchmark package. In WSL/Linux install it with "
            "`pip install -e /path/to/skill-repair-benchmark`."
        ) from exc
    _install_tatu_anthropic_provider(model)
    if prebuilt_images_manifest is not None:
        _install_prebuilt_image_runtime(
            manifest_path=prebuilt_images_manifest,
            tasks_root=tasks_root,
        )
    options: dict[str, Any] = {
        "tasks_root": tasks_root,
        "jobs_root": jobs_root,
        "model": model,
        "reasoning_effort": reasoning_effort,
        "verifier_proxy_mode": verifier_proxy_mode,
    }
    if text_only_retry_limit is not None:
        options["experimental_text_only_retry_limit"] = text_only_retry_limit
    return BenchmarkExecutor(**options)


def _install_tatu_anthropic_provider(model: str) -> None:
    """Register Tatu's Anthropic Messages endpoint for this Python process.

    Tatu lists Claude models on its shared endpoint but does not expose them
    through OpenAI chat completions.  The shared executor requires a qualified
    provider route, while LiteLLM needs the native ``anthropic/`` upstream
    prefix to translate OpenHands' local OpenAI-proxy traffic to ``/messages``.
    This small runtime registration avoids patching the frozen benchmark
    checkout and is activated only by the explicit ``tatu-anthropic/`` route.
    """

    if not model.strip().lower().startswith("tatu-anthropic/"):
        return
    try:
        from benchflow.agents.providers import PROVIDERS, ProviderConfig
    except ImportError as exc:  # pragma: no cover - depends on external repo
        raise RuntimeError("Tatu Anthropic routing requires the shared BenchFlow provider registry.") from exc
    existing = PROVIDERS.get("tatu-anthropic")
    if existing is None:
        PROVIDERS["tatu-anthropic"] = ProviderConfig(
            name="tatu-anthropic",
            # The caller supplies BENCHFLOW_PROVIDER_BASE_URL. This is the
            # same configured Tatu endpoint used by the preflight and keeps
            # credentials outside the model identifier.
            base_url="",
            api_protocol="anthropic-messages",
            auth_type="api_key",
            auth_env="OPENAI_API_KEY",
        )
        return
    if existing.api_protocol != "anthropic-messages":
        raise RuntimeError("The runtime provider name 'tatu-anthropic' is already registered incompatibly.")


def _install_prebuilt_image_runtime(*, manifest_path: str | Path, tasks_root: str | Path) -> None:
    """Bind a frozen local image manifest to the public executor.

    The shared executor already supports ``environment.docker_image``.  This
    adapter hook supplies that value without mutating the frozen task files,
    and changes teardown *only* for these prebuilt-image sandboxes: containers
    and volumes are discarded but the immutable image is retained.

    The hook is deliberately process-local.  It does not patch the installed
    benchmark repository on disk and therefore remains opt-in through the
    ``--unified-prebuilt-images`` CLI option.
    """

    try:
        from benchmark_executor import executor as executor_module
        from benchflow._utils.task_authoring import task_digest
        from benchflow.environment.manifest import EnvironmentManifest
        from benchflow.sandbox.docker import DockerSandbox
        from benchflow.task.paths import SandboxPaths
    except ImportError as exc:  # pragma: no cover - depends on external repo
        raise RuntimeError(
            "Prebuilt unified execution requires the shared skill-repair-benchmark package."
        ) from exc

    manifest_file = Path(manifest_path).expanduser().resolve(strict=True)
    payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(payload.get("tasks"), dict):
        raise ValueError(
            f"Invalid prebuilt image manifest: {manifest_file}. "
            "Expected schema_version=1 and a tasks mapping."
        )

    frozen_tasks_root = Path(tasks_root).expanduser().resolve(strict=True)
    images: dict[str, dict[str, str]] = {}
    for task_id, item in payload["tasks"].items():
        if not isinstance(task_id, str) or not isinstance(item, dict):
            raise ValueError(f"Invalid prebuilt image entry in {manifest_file}: {task_id!r}")
        image = item.get("image")
        task_digest_value = item.get("task_digest")
        image_id = item.get("image_id")
        if not all(isinstance(value, str) and value for value in (image, task_digest_value, image_id)):
            raise ValueError(f"Incomplete prebuilt image entry for {task_id!r} in {manifest_file}")
        images[task_id] = {
            "image": image,
            "task_digest": task_digest_value,
            "image_id": image_id,
        }

    missing_or_changed: list[str] = []
    for task_id, item in sorted(images.items()):
        task_path = frozen_tasks_root / task_id
        if not task_path.is_dir():
            missing_or_changed.append(f"{task_id}: task directory missing")
            continue
        if task_digest(task_path) != item["task_digest"]:
            missing_or_changed.append(f"{task_id}: task files differ from prebuild manifest")
            continue
        inspected = subprocess.run(
            ["docker", "image", "inspect", "--format", "{{.Id}}", item["image"]],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if inspected.returncode != 0:
            missing_or_changed.append(f"{task_id}: image missing ({item['image']})")
        elif inspected.stdout.strip() != item["image_id"]:
            missing_or_changed.append(f"{task_id}: image ID differs ({item['image']})")
    if missing_or_changed:
        rendered = "\n- ".join(missing_or_changed)
        raise RuntimeError(
            "Prebuilt image manifest cannot be used:\n- "
            f"{rendered}\nRebuild with scripts/prebuild_unified_core25_images.py."
        )

    original_manifest_loader = executor_module._environment_manifest_from_task_document
    if not getattr(executor_module, "_skillrevise_prebuilt_manifest_installed", False):
        def _manifest_loader(task_path: Path):
            item = images.get(task_path.name)
            if item is None:
                return original_manifest_loader(task_path)
            observed_digest = task_digest(task_path)
            if observed_digest != item["task_digest"]:
                raise RuntimeError(
                    f"Task {task_path.name!r} changed after prebuild; refusing to run a stale image."
                )
            return EnvironmentManifest(
                name=f"skillrevise-prebuilt-{task_path.name}",
                image=item["image"],
            )

        executor_module._environment_manifest_from_task_document = _manifest_loader
        executor_module._skillrevise_prebuilt_manifest_installed = True

    if getattr(DockerSandbox, "_skillrevise_preserve_prebuilt_images", False):
        return

    original_stop = DockerSandbox.stop

    async def _stop_preserving_prebuilt_image(self, delete: bool) -> None:
        # Non-prebuilt tasks retain the shared executor's exact lifecycle.
        if not getattr(self, "_use_prebuilt", False) or not delete or self._keep_containers:
            await original_stop(self, delete)
            return
        try:
            await __import__("asyncio").wait_for(
                self._chown_to_host_user(str(SandboxPaths.logs_dir), recursive=True), timeout=30
            )
        except TimeoutError:
            self.logger.warning("Chown logs directory timed out; continuing teardown.")
        except Exception as exc:  # pragma: no cover - external Docker behavior
            self.logger.warning("Failed to chown logs directory: %s", exc)
        try:
            # This intentionally omits ``--rmi all``.  Compose still deletes
            # rollout containers, task volumes, networks and writable layers.
            await self._run_docker_compose_command(
                ["down", "--volumes", "--remove-orphans", "-t", "5"], timeout_sec=120
            )
        except Exception as exc:  # pragma: no cover - external Docker behavior
            self.logger.warning("Docker compose down hung/failed (%s); force-killing project.", exc)
            await self._force_kill_project()

    DockerSandbox.stop = _stop_preserving_prebuilt_image
    DockerSandbox._skillrevise_preserve_prebuilt_images = True


@dataclass(frozen=True)
class CandidateBundle:
    """An immutable method-skill bundle associated with one Skill version."""

    root: Path
    sha256: str
    target_skill: str


class SkillBundleMaterializer:
    """Create complete, immutable method-skill bundles for one frozen task set.

    ``replace-original`` starts from the task's official ``environment/skills``
    bundle and replaces one selected ``SKILL.md``. ``generated-only`` creates
    a fresh bundle containing only SkillRevise's LLM-authored Skill. The latter
    is the paper-style v0 -> v1 -> v2 -> v3 protocol: it does not read or
    expose any benchmark-provided Skill as an authoring prior.
    """

    def __init__(
        self,
        *,
        tasks_root: str | Path,
        candidates_root: str | Path,
        target_skill_by_task: Mapping[str, str] | None = None,
        bundle_mode: str = "replace-original",
    ) -> None:
        self.tasks_root = Path(tasks_root).expanduser().resolve()
        self.candidates_root = Path(candidates_root).expanduser().resolve()
        self.target_skill_by_task = dict(target_skill_by_task or {})
        if bundle_mode not in {"replace-original", "generated-only"}:
            raise ValueError(f"Unsupported unified skill bundle mode: {bundle_mode!r}")
        self.bundle_mode = bundle_mode

    def materialize(self, task: TaskSpec, skill: Skill) -> CandidateBundle:
        source: Path | None = None
        overrides = self._bundle_overrides(skill)
        if self.bundle_mode == "generated-only":
            self._task_dir(task.task_id)
            target_relpath = Path("skillrevise") / "SKILL.md"
        else:
            source = self._official_bundle(task.task_id)
            target_relpath = self._skill_target_from_metadata(skill, source) or self._target_skill_path(
                task.task_id, source
            )
        markdown = skill.as_markdown().replace("\r\n", "\n")
        overrides[target_relpath.as_posix()] = markdown
        digest_payload = json.dumps(
            {"target": target_relpath.as_posix(), "overrides": overrides},
            ensure_ascii=False,
            sort_keys=True,
        )
        digest = hashlib.sha256(digest_payload.encode("utf-8")).hexdigest()[:16]
        bundle = (
            self.candidates_root
            / task.task_id
            / f"{_safe_component(skill.version)}-{digest}"
            / "full-skills"
        )

        if bundle.exists():
            self._assert_existing_bundle(bundle, overrides)
        else:
            bundle.parent.mkdir(parents=True, exist_ok=True)
            if source is None:
                bundle.mkdir()
            else:
                shutil.copytree(source, bundle, symlinks=True)
            for relative_path, content in overrides.items():
                target = bundle / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            self._validate_bundle(bundle)

        return CandidateBundle(
            root=bundle,
            sha256=_bundle_sha256(bundle),
            target_skill=target_relpath.as_posix(),
        )

    def with_original_skill_context(self, task: TaskSpec) -> TaskSpec:
        """Return a TaskSpec whose author/reviser can see the repair target.

        The current SkillRevise prompt API receives a ``TaskSpec`` rather than
        a bundle object.  Carrying the selected official markdown in task
        context lets authoring produce a replacement for the real Skill
        instead of an unrelated standalone template.
        """

        if self.bundle_mode == "generated-only":
            raise ValueError(
                "generated-only candidate bundles intentionally do not expose an official Skill "
                "to authoring; use the task instruction as the v0 source."
            )
        source = self._official_bundle(task.task_id)
        target_relpath = self._target_skill_path(task.task_id, source)
        context = dict(task.context)
        metadata = dict(task.metadata)
        context["original_skill_markdown"] = (source / target_relpath).read_text(encoding="utf-8")
        context["original_skill_relpath"] = target_relpath.as_posix()
        metadata["unified_task_dir"] = str(self.tasks_root / task.task_id)
        return replace(task, context=context, metadata=metadata)

    def skill_paths(self, task_id: str) -> list[str]:
        """Return every repairable official ``SKILL.md`` path for a task."""

        if self.bundle_mode != "replace-original":
            raise ValueError("A generated-only bundle has no official Skill catalog.")
        bundle = self._official_bundle(task_id)
        return [path.relative_to(bundle).as_posix() for path in sorted(bundle.rglob("SKILL.md"))]

    def official_bundle_path(self, task_id: str) -> Path:
        """Return the read-only official bundle path for inspection only."""

        if self.bundle_mode != "replace-original":
            raise ValueError("A generated-only bundle has no official Skill bundle.")
        return self._official_bundle(task_id)

    def with_skill_context(
        self,
        task: TaskSpec,
        target_skill: str,
        *,
        overrides: Mapping[str, str] | None = None,
    ) -> TaskSpec:
        """Expose one frozen Skill while retaining the full bundle as execution state.

        ``overrides`` are prior accepted revisions in a bundle-repair branch.
        They are deliberately carried in metadata rather than written into the
        task checkout; :meth:`materialize` creates an immutable copy for every
        rollout.
        """

        source = self._official_bundle(task.task_id)
        target = self._validated_relative_skill_path(source, target_skill)
        current = dict(overrides or {}).get(target.as_posix())
        context = dict(task.context)
        metadata = dict(task.metadata)
        context["original_skill_markdown"] = (
            current if current is not None else (source / target).read_text(encoding="utf-8")
        )
        context["original_skill_relpath"] = target.as_posix()
        metadata["unified_task_dir"] = str(self.tasks_root / task.task_id)
        metadata["bundle_target_relpath"] = target.as_posix()
        metadata["bundle_overrides"] = dict(overrides or {})
        return replace(task, context=context, metadata=metadata)

    def _task_dir(self, task_id: str) -> Path:
        task_dir = self.tasks_root / task_id
        if not task_dir.is_dir():
            raise ValueError(
                f"Unified task {task_id!r} was not found below {self.tasks_root}. "
                "Use the project group's frozen SkillsBench task checkout."
            )
        return task_dir

    def _official_bundle(self, task_id: str) -> Path:
        task_dir = self._task_dir(task_id)
        bundle = task_dir / "environment" / "skills"
        if not bundle.is_dir():
            raise ValueError(
                f"Task {task_id!r} has no environment/skills bundle. "
                "It cannot be used as an original-Skill repair task."
            )
        return bundle

    def _target_skill_path(self, task_id: str, bundle: Path) -> Path:
        configured = self.target_skill_by_task.get(task_id)
        if configured:
            target = Path(configured)
            if target.is_absolute() or ".." in target.parts or target.name != "SKILL.md":
                raise ValueError(
                    f"Invalid target Skill path for {task_id!r}: {configured!r}. "
                    "It must be a relative path ending in SKILL.md."
                )
            if not (bundle / target).is_file():
                raise ValueError(
                    f"Configured target Skill does not exist for {task_id!r}: {configured}"
                )
            return target

        candidates = sorted(path.relative_to(bundle) for path in bundle.rglob("SKILL.md"))
        if len(candidates) != 1:
            rendered = ", ".join(path.as_posix() for path in candidates) or "none"
            raise ValueError(
                f"Task {task_id!r} has {len(candidates)} SKILL.md files ({rendered}). "
                "Pass an explicit task_id=relative/path/SKILL.md mapping."
            )
        return candidates[0]

    def _assert_existing_bundle(self, bundle: Path, overrides: Mapping[str, str]) -> None:
        for relative_path, content in overrides.items():
            target = bundle / relative_path
            if not target.is_file() or target.read_text(encoding="utf-8") != content:
                raise RuntimeError(
                    f"Refusing to overwrite immutable candidate bundle {bundle}. "
                    "Change the Skill content/version or use a new candidates root."
                )
        self._validate_bundle(bundle)

    def _skill_target_from_metadata(self, skill: Skill, bundle: Path) -> Path | None:
        value = skill.metadata.get("bundle_target_relpath")
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("Skill metadata bundle_target_relpath must be a string.")
        return self._validated_relative_skill_path(bundle, value)

    def _bundle_overrides(self, skill: Skill) -> dict[str, str]:
        raw = skill.metadata.get("bundle_overrides", {})
        if raw is None:
            return {}
        if not isinstance(raw, Mapping):
            raise ValueError("Skill metadata bundle_overrides must be a mapping.")
        result: dict[str, str] = {}
        for relative_path, content in raw.items():
            if not isinstance(relative_path, str) or not isinstance(content, str):
                raise ValueError("bundle_overrides must map relative paths to markdown strings.")
            result[relative_path] = content.replace("\r\n", "\n")
        return result

    @staticmethod
    def _validated_relative_skill_path(bundle: Path, value: str) -> Path:
        target = Path(value)
        if target.is_absolute() or ".." in target.parts or target.name != "SKILL.md":
            raise ValueError(f"Invalid target Skill path: {value!r}")
        if not (bundle / target).is_file():
            raise ValueError(f"Target Skill does not exist: {value}")
        return target

    @staticmethod
    def _validate_bundle(bundle: Path) -> None:
        if not bundle.is_dir():
            raise ValueError(f"Candidate bundle is not a directory: {bundle}")
        files = [path for path in bundle.rglob("*") if path.is_file()]
        if not any(path.name == "SKILL.md" for path in files):
            raise ValueError(f"Candidate bundle contains no SKILL.md: {bundle}")
        for path in bundle.rglob("*"):
            if path.is_symlink():
                raise ValueError(f"Candidate bundle must not contain symlinks: {path}")
        for path in files:
            if path.name == "SKILL.md":
                path.read_text(encoding="utf-8")


class UnifiedBenchmarkAdapter(AgentAdapter):
    """Use the shared executor as SkillRevise's real-task adapter.

    ``None`` maps to the standard no-skill condition.  A concrete ``Skill``
    maps to method-skill and is first materialized as a full immutable bundle.
    Original-Skill is exposed by :meth:`run_original_skill` because the local
    AgentAdapter protocol only distinguishes no-skill from a method Skill.
    """

    def __init__(
        self,
        *,
        executor: _ExecutorProtocol,
        bundle_materializer: SkillBundleMaterializer,
        method_id: str = "skillrevise",
    ) -> None:
        self.executor = executor
        self.bundle_materializer = bundle_materializer
        self.method_id = _safe_component(method_id)

    def run(self, task: TaskSpec, skill: Skill | None) -> ExecutionTrace:
        if skill is None:
            return self._run_condition(task, skill=None, condition="no-skill", stage="no-skill")
        return self._run_condition(task, skill=skill, condition="method-skill", stage=skill.version)

    def run_original_skill(self, task: TaskSpec) -> ExecutionTrace:
        """Run the official task bundle under the executor's original-skill condition."""

        return self._run_condition(task, skill=None, condition="original-skill", stage="original-skill")

    def _run_condition(
        self,
        task: TaskSpec,
        *,
        skill: Skill | None,
        condition: str,
        stage: str,
    ) -> ExecutionTrace:
        bundle: CandidateBundle | None = None
        if condition == "method-skill":
            if skill is None:
                raise AssertionError("method-skill requires a Skill")
            bundle = self.bundle_materializer.materialize(task, skill)

        rollout_id = _rollout_id(task.task_id, stage)
        started = datetime.now(timezone.utc)
        try:
            result = self.executor.run(
                task_id=task.task_id,
                method_id=self.method_id,
                stage=stage,
                rollout_id=rollout_id,
                condition=condition,
                skill_bundle=None if bundle is None else bundle.root,
            )
        except Exception as exc:
            return _infrastructure_trace(
                task=task,
                skill=skill,
                run_id=rollout_id,
                started=started,
                summary=f"Shared benchmark executor raised {type(exc).__name__}: {exc}",
                metadata={"executor_error": repr(exc), "comparable": False},
            )
        return _trace_from_benchmark_result(
            task=task,
            skill=skill,
            result=result,
            run_id=rollout_id,
            started=started,
            candidate_bundle=bundle,
        )


def _trace_from_benchmark_result(
    *,
    task: TaskSpec,
    skill: Skill | None,
    result: Any,
    run_id: str,
    started: datetime,
    candidate_bundle: CandidateBundle | None,
) -> ExecutionTrace:
    execution_ok = bool(getattr(result, "execution_ok", False))
    # `comparable` was a legacy executor field.  Protocol v2 intentionally
    # reports validity through `execution_ok`; treating an absent legacy field
    # as false incorrectly turns completed task failures into infrastructure
    # errors and discards their rewards.
    legacy_comparable = getattr(result, "comparable", None)
    comparable = execution_ok if legacy_comparable is None else bool(legacy_comparable)
    task_passed = getattr(result, "task_passed", None)
    wall_time = _finite_number(getattr(result, "wall_time_sec", None)) or 0.0
    ended = started + timedelta(seconds=wall_time)
    result_dict = _result_dict(result)
    reward = getattr(result, "reward", None)
    exposure = getattr(result, "skill_exposure", None)
    metadata: dict[str, Any] = {
        "reward": reward if comparable else None,
        "comparable": comparable,
        "execution_ok": execution_ok,
        "protocol_evidence_valid": bool(getattr(result, "protocol_evidence_valid", False)),
        "trajectory_complete": bool(getattr(result, "trajectory_complete", False)),
        "iteration_accounting_complete": bool(
            getattr(result, "iteration_accounting_complete", False)
        ),
        "provider_requests": getattr(result, "provider_requests", None),
        "agent_iterations": getattr(result, "agent_iterations", None),
        "cost_usd": getattr(result, "cost_usd", None),
        "termination_reason": getattr(result, "termination_reason", None),
        "benchmark_result": result_dict,
        "skill_exposure": {
            "verified": getattr(exposure, "verified", None),
            "expected_bundle_sha256": getattr(exposure, "expected_bundle_sha256", None),
            "observed_bundle_sha256": getattr(exposure, "observed_bundle_sha256", None),
            "expected_skill_count": getattr(exposure, "expected_skill_count", None),
            "observed_skill_count": getattr(exposure, "observed_skill_count", None),
        },
    }
    if candidate_bundle is not None:
        metadata["candidate_bundle"] = {
            "root": str(candidate_bundle.root),
            "sha256": candidate_bundle.sha256,
            "target_skill": candidate_bundle.target_skill,
        }

    if not comparable:
        metadata.update(
            {
                "executor_error": getattr(result, "error", None),
                "verifier_error": getattr(result, "verifier_error", None),
                "error_category": getattr(result, "error_category", None),
                "verifier_error_category": getattr(result, "verifier_error_category", None),
            }
        )
        summary = _uncomparable_summary(result)
        return _infrastructure_trace(
            task=task,
            skill=skill,
            run_id=run_id,
            started=started,
            summary=summary,
            metadata=metadata,
            latency_seconds=wall_time,
            events=_trajectory_events(getattr(result, "trajectory", ())),
        )

    passed = bool(task_passed)
    return ExecutionTrace(
        run_id=run_id,
        task_id=task.task_id,
        skill_version=None if skill is None else skill.version,
        success=passed,
        status="success" if passed else "failure",
        started_at=started.isoformat(),
        ended_at=ended.isoformat(),
        # The unified public result does not promise a token total.  Do not
        # invent one; callers should use the success-only preset for selection.
        tokens=0,
        tool_calls=_nonnegative_int(getattr(result, "provider_requests", None)),
        steps=_nonnegative_int(getattr(result, "agent_iterations", None)),
        latency_seconds=wall_time,
        outcome_summary=_comparable_summary(result, passed),
        events=_trajectory_events(getattr(result, "trajectory", ())),
        metadata=metadata,
    )


def _infrastructure_trace(
    *,
    task: TaskSpec,
    skill: Skill | None,
    run_id: str,
    started: datetime,
    summary: str,
    metadata: dict[str, Any],
    latency_seconds: float = 0.0,
    events: list[TrajectoryEvent] | None = None,
) -> ExecutionTrace:
    ended = started + timedelta(seconds=latency_seconds)
    metadata = dict(metadata)
    metadata.setdefault("reward", None)
    metadata.setdefault("comparable", False)
    metadata.setdefault("infrastructure_error", True)
    return ExecutionTrace(
        run_id=run_id,
        task_id=task.task_id,
        skill_version=None if skill is None else skill.version,
        success=False,
        status="infrastructure_error",
        started_at=started.isoformat(),
        ended_at=ended.isoformat(),
        tokens=0,
        tool_calls=0,
        steps=0,
        latency_seconds=latency_seconds,
        outcome_summary=summary,
        events=events or [],
        metadata=metadata,
    )


def _trajectory_events(trajectory: Any) -> list[TrajectoryEvent]:
    events: list[TrajectoryEvent] = []
    if not isinstance(trajectory, (list, tuple)):
        return events
    for index, item in enumerate(trajectory, start=1):
        payload = item if isinstance(item, dict) else {"value": str(item)}
        kind = str(payload.get("kind") or payload.get("type") or payload.get("event") or "trajectory")
        summary = str(
            payload.get("summary")
            or payload.get("message")
            or payload.get("content")
            or payload.get("event")
            or kind
        )
        events.append(
            TrajectoryEvent(
                step_index=index,
                kind=kind,
                summary=summary[:4000],
                evidence=json.dumps(payload, ensure_ascii=False, default=str)[:12000],
                metadata={"source": "shared-benchmark-executor"},
            )
        )
    return events


def _result_dict(result: Any) -> dict[str, Any]:
    to_dict = getattr(result, "to_dict", None)
    if callable(to_dict):
        value = to_dict()
        if isinstance(value, dict):
            return value
    return {"repr": repr(result)}


def _uncomparable_summary(result: Any) -> str:
    details = [
        getattr(result, "error", None),
        getattr(result, "verifier_error", None),
        getattr(result, "export_error", None),
        getattr(result, "termination_reason", None),
    ]
    detail = next((str(value) for value in details if value), "missing protocol evidence")
    return f"Shared benchmark rollout is not comparable: {detail}"


def _comparable_summary(result: Any, passed: bool) -> str:
    reason = getattr(result, "termination_reason", None)
    verdict = "passed" if passed else "failed official verifier"
    return f"Shared benchmark rollout {verdict}" + (f" (stop: {reason})" if reason else "")


def _bundle_sha256(bundle: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted((item for item in bundle.rglob("*") if item.is_file()), key=lambda item: item.as_posix()):
        relative = path.relative_to(bundle).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        content = path.read_bytes()
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return f"sha256:{digest.hexdigest()}"


def _safe_component(value: str) -> str:
    cleaned = str(value).strip()
    if not cleaned or cleaned in {".", ".."} or "/" in cleaned or "\\" in cleaned:
        raise ValueError(f"Expected a safe path component, got {value!r}")
    return cleaned


def _rollout_id(task_id: str, stage: str) -> str:
    task_part = _safe_component(task_id)[:48]
    stage_part = _safe_component(stage)[:32]
    return f"{task_part}-{stage_part}-{uuid4().hex[:12]}"


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _nonnegative_int(value: Any) -> int:
    if isinstance(value, bool) or value is None:
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0
