"""Opt-in process-local reuse of validated JPG candidate executions."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path


def load_candidate(adapter, task, skill, stage, run_root, model, protocol, digest, loader):
    """Match persisted identity and reload canonical evidence, never choose best-of."""
    from skillrevise.benchmarks.unified_executor_adapter import _trace_from_benchmark_result
    bundle = adapter.bundle_materializer.materialize(task, skill)
    matches = []
    for request_file in sorted((Path(run_root) / "jobs" / adapter.method_id).glob("*/executor_request.json")):
        request = json.loads(request_file.read_text(encoding="utf-8"))
        if (request.get("task_id") != task.task_id or request.get("method_id") != adapter.method_id
                or request.get("stage") != stage or request.get("condition") != "method-skill"
                or request.get("model_selection", {}).get("model") != model
                or request.get("model_selection", {}).get("reasoning_effort") is not None
                or request.get("protocol") != protocol or request.get("task_digest") != digest
                or request.get("verifier_proxy", {}).get("mode") != "off"
                or request.get("skill_bundle_manifest", {}).get("skill_bundle_sha256") != bundle.sha256):
            continue
        folder = request_file.parent
        summary_path = folder / "benchmark_result.json"
        if not summary_path.is_file():
            continue
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if not summary.get("execution_ok") or summary.get("model") != model:
            continue
        expected_endpoint = os.environ.get("BENCHFLOW_PROVIDER_BASE_URL")
        if expected_endpoint and summary.get("provider_base_url", "").rstrip("/") != expected_endpoint.rstrip("/"):
            continue
        result = loader(folder / "result.json", request_json=request_file,
            task_id=task.task_id, rollout_id=request["rollout_id"], method_id=adapter.method_id,
            stage=stage, protocol_id=protocol["protocol_id"], expected_model=model, expected_reasoning_effort=None)
        if not (result.execution_ok and result.protocol_evidence_valid and result.trajectory_complete
                and result.iteration_accounting_complete and result.skill_exposure.verified):
            continue
        if result.reward != summary.get("reward"):
            raise RuntimeError("Canonical reward differs from persisted summary; refusing checkpoint reuse")
        matches.append((request, result))
    if len(matches) > 1:
        raise RuntimeError("Multiple valid matching JPG candidate executions; pin one explicitly before resuming")
    if not matches:
        return None
    request, result = matches[0]
    trace = _trace_from_benchmark_result(task=task, skill=skill, result=result,
        run_id=request["rollout_id"], started=datetime.fromisoformat(request["created_at"]), candidate_bundle=bundle)
    receipt = Path(run_root) / "evidence/execution_resume" / (uuid.uuid4().hex + ".json")
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps({"source_rollout_id": trace.run_id, "reward": result.reward,
        "bundle_sha256": bundle.sha256, "new_agent_execution": False,
        "match": "model, endpoint, task digest, stage, method, protocol, bundle hash, validated canonical evidence"}, indent=2), encoding="utf-8")
    print(f"[JPG resume] Reused valid candidate {trace.run_id}; reward={result.reward}; no Agent execution.", flush=True)
    return trace


def install_candidate_resume(run_root, *, model, method_id):
    from benchflow._utils.task_authoring import task_digest
    from benchflow.benchmark_executor import protocol_descriptor
    from benchmark_executor.result import BenchmarkResult
    from skillrevise.benchmarks.unified_executor_adapter import UnifiedBenchmarkAdapter
    original = UnifiedBenchmarkAdapter._run_condition
    if getattr(original, "_jpg_resume_installed", False):
        return

    def run(self, task, *, skill, condition, stage):
        if task.task_id == "jpg-ocr-stat" and skill is not None and condition == "method-skill" and self.method_id == method_id:
            trace = load_candidate(self, task, skill, stage, run_root, model, protocol_descriptor(),
                task_digest(self.bundle_materializer.tasks_root / task.task_id), BenchmarkResult.from_result_json)
            if trace is not None:
                return trace
        return original(self, task, skill=skill, condition=condition, stage=stage)

    run._jpg_resume_installed = True
    UnifiedBenchmarkAdapter._run_condition = run
