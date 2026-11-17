"""Launch or preflight one isolated JPG SkillGrad S1 rollout."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-root", type=Path, required=True)
    parser.add_argument("--jobs-root", type=Path, required=True)
    parser.add_argument("--skill-bundle", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--stage", default="S1")
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()

    os.environ["BENCHFLOW_DOTENV_PATH"] = str(args.env_file.resolve(strict=True))
    from benchflow._dotenv import load_dotenv_env
    from benchflow.agents.env import resolve_agent_env
    from benchflow.benchmark_executor import (
        EXECUTOR_PROTOCOL_ID,
        MAX_PARENT_ITERATIONS_PER_STEP,
        build_skill_bundle_manifest,
    )
    from benchflow.providers.litellm_config import resolve_litellm_route
    from benchflow.task import Task
    from benchflow._utils.task_authoring import task_digest
    from benchmark_executor import BenchmarkExecutor

    expected_src = Path(os.environ["JPG_EXECUTOR65_SRC"]).resolve(strict=True)
    for module in ("benchflow", "benchmark_executor"):
        actual = Path(sys.modules[module].__file__).resolve()
        if not actual.is_relative_to(expected_src):
            raise RuntimeError(f"{module} was imported outside isolated JPG65 source")
    if MAX_PARENT_ITERATIONS_PER_STEP != 65:
        raise RuntimeError("The isolated executor does not enforce 65 iterations")

    env = load_dotenv_env(args.env_file)
    model_id = env.get("PARATERA_OPUS_MODEL", "").strip()
    if not model_id or "opus" not in model_id.lower():
        raise RuntimeError("Paratera Opus model id is missing or invalid")
    if not env.get("PARATERA_API_KEY", "").strip():
        raise RuntimeError("Paratera API credential is missing")
    if env.get("PARATERA_BASE_URL", "").rstrip("/") != "https://llmapi.paratera.com":
        raise RuntimeError("Paratera endpoint differs from the configured JPG route")

    model = f"paratera/{model_id}"
    route = resolve_litellm_route(model, env)
    if (route.provider_name != "paratera"
            or route.upstream_model != f"openai/{model_id}"
            or route.litellm_params.get("api_base") != env["PARATERA_BASE_URL"]
            or "PARATERA_API_KEY" not in route.required_env):
        raise RuntimeError("Resolved Opus execution route does not match Paratera")

    task_path = (args.task_root / "jpg-ocr-stat").resolve(strict=True)
    task = Task(task_path)
    if task.name != "jpg-ocr-stat":
        raise RuntimeError("Task loader resolved a different task")
    images = sorted((task_path / "environment/workspace/dataset/img").glob("*.jpg"))
    if len(images) != 22:
        raise RuntimeError(f"Expected 22 original JPGs, found {len(images)}")

    manifest = build_skill_bundle_manifest(args.skill_bundle.resolve(strict=True))
    if manifest.skill_count != 5 or manifest.file_count != 18:
        raise RuntimeError("Frozen candidate bundle shape differs from Skill1")
    digest = task_digest(task_path)
    resolved = resolve_agent_env("openhands", model, {})
    if (resolved.get("BENCHFLOW_PROVIDER_NAME") != "paratera"
            or resolved.get("BENCHFLOW_PROVIDER_BASE_URL") != env["PARATERA_BASE_URL"]
            or not resolved.get("LLM_API_KEY")):
        raise RuntimeError("OpenHands provider environment did not resolve to Paratera")
    if shutil.which("docker") is None:
        raise RuntimeError("Docker CLI is unavailable")
    docker = subprocess.run(
        ["docker", "version", "--format", "{{.Server.Version}}"],
        check=True, capture_output=True, text=True, timeout=20,
    ).stdout.strip()

    report = {
        "preflight": "PASS",
        "python": sys.version.split()[0],
        "benchflow_module": str(Path(sys.modules["benchflow"].__file__).resolve()),
        "benchmark_executor_module": str(Path(sys.modules["benchmark_executor"].__file__).resolve()),
        "executor_protocol": EXECUTOR_PROTOCOL_ID,
        "max_parent_iterations_per_step": MAX_PARENT_ITERATIONS_PER_STEP,
        "model_route": model,
        "provider_route": route.provider_name,
        "upstream_model": route.upstream_model,
        "provider_base_url": route.litellm_params.get("api_base"),
        "credential_present": True,
        "task_digest": digest,
        "task_images": len(images),
        "skill_bundle_sha256": manifest.sha256,
        "skill_bundle_file_count": manifest.file_count,
        "skill_count": manifest.skill_count,
        "docker_server": docker,
        "run_id": args.run_id,
        "stage": args.stage,
        "model_request_sent": False,
    }
    if args.preflight:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    executor = BenchmarkExecutor(
        tasks_root=args.task_root,
        jobs_root=args.jobs_root,
        model=model,
        protocol=EXECUTOR_PROTOCOL_ID,
    )
    result = asyncio.run(executor.run_async(
        task_id="jpg-ocr-stat",
        method_id="skillgrad-jpg-opus47",
        stage=args.stage,
        rollout_id=args.run_id,
        condition="method-skill",
        skill_bundle=args.skill_bundle,
    ))
    summary = {
        "preflight": "PASS",
        "run_id": args.run_id,
        "model_request_sent": bool(result.provider_requests),
        "execution_ok": result.execution_ok,
        "task_passed": result.task_passed,
        "reward": result.reward,
        "verifier_components": result.verifier_components,
        "agent_iterations": result.agent_iterations,
        "iteration_accounting_complete": result.iteration_accounting_complete,
        "termination_reason": result.termination_reason,
        "provider_requests": result.provider_requests,
        "cost_usd": result.cost_usd,
        "protocol_evidence_valid": result.protocol_evidence_valid,
        "trajectory_complete": result.trajectory_complete,
        "error_category": result.error_category,
        "verifier_error_category": result.verifier_error_category,
        "export_error": result.export_error,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if result.protocol_evidence_valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
