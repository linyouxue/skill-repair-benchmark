from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from adapters.common.paths import ROOT, benchmark_executor_root, tasks_root


def _load_project_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_benchmark_executor_class():
    src = benchmark_executor_root() / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    from benchmark_executor import BenchmarkExecutor

    return BenchmarkExecutor


def _expand_env_refs() -> None:
    for key, value in list(os.environ.items()):
        if value.startswith("${") and value.endswith("}"):
            ref = value[2:-1]
            os.environ[key] = os.environ.get(ref, value)


def _bridge_model_provider_env() -> None:
    _expand_env_refs()
    provider = os.environ.get("MODEL_PROVIDER", "").strip().lower()
    tatu_secret = os.environ.get("TATU_API_KEY", "").strip()
    tatu_base = os.environ.get("TATU_BASE_URL", "").strip()
    tatu_model = os.environ.get("TATU_MODEL", "").strip()
    ai360_secret = (
        os.environ.get("AI360_API_KEY", "").strip()
        or os.environ.get("LLM_API_KEY", "").strip()
        or os.environ.get("OPENAI_API_KEY", "").strip()
    )
    ai360_base = (
        os.environ.get("AI360_BASE_URL", "").strip()
        or os.environ.get("LLM_API_BASE", "").strip()
        or os.environ.get("OPENAI_API_BASE", "").strip()
        or os.environ.get("OPENAI_BASE_URL", "").strip()
    )
    ai360_model = os.environ.get("AI360_MODEL", "").strip()

    use_tatu = provider == "tatu" or (bool(tatu_secret and tatu_base) and not ai360_secret)
    if use_tatu:
        secret, base_url, model = tatu_secret, tatu_base, tatu_model
        if secret:
            os.environ["TATU_API_KEY"] = secret
            os.environ["OPENAI_API_KEY"] = secret
        if base_url:
            os.environ["TATU_BASE_URL"] = base_url
            os.environ["OPENAI_API_BASE"] = base_url
            os.environ["OPENAI_BASE_URL"] = base_url
            os.environ["SKILLOPT_API_BASE"] = base_url
        if model:
            os.environ["TATU_MODEL"] = model
            os.environ["SKILLOPT_MODEL"] = model
            benchmark = os.environ.get("BENCHMARK_MODEL", "").strip()
            if not benchmark or benchmark in {"tatu/${TATU_MODEL}", "ai360/${AI360_MODEL}"}:
                os.environ["BENCHMARK_MODEL"] = f"tatu/{model}"
        return

    secret, base_url, model = ai360_secret, ai360_base, ai360_model
    if secret:
        os.environ.setdefault("AI360_API_KEY", secret)
        os.environ.setdefault("OPENAI_API_KEY", secret)
    if base_url:
        os.environ.setdefault("AI360_BASE_URL", base_url)
        os.environ.setdefault("OPENAI_API_BASE", base_url)
        os.environ.setdefault("OPENAI_BASE_URL", base_url)
    if model and os.environ.get("BENCHMARK_MODEL", "").strip() == "ai360/${AI360_MODEL}":
        os.environ["BENCHMARK_MODEL"] = f"ai360/{model}"


def new_executor(jobs_root: Path):
    _load_project_env()
    _bridge_model_provider_env()
    if os.environ.get("DEBUG", "").strip().lower() not in {"", "0", "1", "true", "false", "yes", "no", "on", "off"}:
        os.environ.pop("DEBUG", None)
    BenchmarkExecutor = load_benchmark_executor_class()
    install_timeout_raw = os.environ.get("SKILLOPT_EVA_AGENT_INSTALL_TIMEOUT", "").strip()
    if install_timeout_raw:
        try:
            install_timeout = int(install_timeout_raw)
        except ValueError as exc:
            raise ValueError("SKILLOPT_EVA_AGENT_INSTALL_TIMEOUT must be an integer") from exc
        if install_timeout < 1:
            raise ValueError("SKILLOPT_EVA_AGENT_INSTALL_TIMEOUT must be >= 1")
        # BenchFlow records this same registry value in config.json, so the
        # enforced timeout and reported timeout remain identical.
        from benchflow.agents.registry import AGENTS

        AGENTS["openhands"].install_timeout = install_timeout
    model = os.environ.get("BENCHMARK_MODEL", "").strip()
    if not model:
        raise RuntimeError("BENCHMARK_MODEL is not set. Source .env before running.")
    reasoning_effort = os.environ.get("BENCHMARK_REASONING_EFFORT", "").strip() or None
    return BenchmarkExecutor(
        tasks_root=tasks_root(),
        jobs_root=jobs_root,
        model=model,
        reasoning_effort=reasoning_effort,
        protocol="skillrepair-v1",
    )


def timestamp_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_original(task_id: str, run_id: str) -> dict[str, Any]:
    jobs_root = ROOT / "experiments" / run_id / "jobs"
    rollout_id = f"{task_id}-original-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
    result = new_executor(jobs_root).run(
        task_id=task_id,
        condition="original-skill",
        method_id="baseline-original-skill",
        stage="original-skill",
        rollout_id=rollout_id,
    )
    data = result.to_dict()
    out_dir = ROOT / "experiments" / run_id / "baseline" / "original-skill" / task_id
    write_json(out_dir / "benchmark_result.json", data)
    write_json(out_dir / "rollout_pointer.json", {"method_id": "baseline-original-skill", "rollout_id": rollout_id})
    return data


def run_method_skill(
    *,
    task_id: str,
    method_id: str,
    run_id: str,
    skill_bundle: Path,
    stage: str = "round-1",
    persist_method_result: bool = True,
) -> dict[str, Any]:
    jobs_root = ROOT / "experiments" / run_id / "jobs"
    rollout_id = f"{task_id}-{method_id}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
    result = new_executor(jobs_root).run(
        task_id=task_id,
        condition="method-skill",
        skill_bundle=skill_bundle,
        method_id=method_id,
        stage=stage,
        rollout_id=rollout_id,
    )
    data = result.to_dict()
    if persist_method_result:
        out_dir = ROOT / "experiments" / run_id / "methods" / method_id / task_id
        write_json(out_dir / "method_result.json", data)
        write_json(out_dir / "rollout_pointer.json", {"method_id": method_id, "rollout_id": rollout_id})
    return data
