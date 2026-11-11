"""Process-scoped JPG execution hooks; no edits to the shared executor checkout."""
from __future__ import annotations

import hashlib
import importlib
import json
import logging
import shutil
from pathlib import Path


def set_final_iteration_cap() -> dict:
    """Propagate the JPG-specific 65 cap through env, metadata and validation."""
    modules = [importlib.import_module(name) for name in (
        "benchflow.benchmark_executor", "benchflow.acp.runtime", "benchmark_executor.result",
    )]
    before = {}
    for module in modules:
        current = getattr(module, "MAX_PARENT_ITERATIONS_PER_STEP", None)
        if current not in (60, 65):
            raise RuntimeError(f"Unexpected iteration policy in {module.__name__}: {current}")
        before[module.__name__] = current
    for module in modules:
        module.MAX_PARENT_ITERATIONS_PER_STEP = 65
    policy = modules[0]
    env = policy.apply_openhands_executor_env("openhands", {}, skill_policy=None, manifest=None)
    if env["BENCHMARK_EXECUTOR_MAX_ITERATIONS"] != "65" or policy.protocol_descriptor()["max_parent_iterations_per_step"] != 65:
        raise RuntimeError("65-iteration propagation failed")
    return {"scope": "current_JPG_final_process_only", "previous_values": before, "max_parent_iterations": 65}


def install_excel_export_hook() -> None:
    """Download actual output before verifier hardening/teardown; never generate an Excel."""
    from benchflow.rollout import Rollout
    if getattr(Rollout, "_jpg_excel_export_installed", False):
        return
    original = Rollout.verify

    async def verify_with_export(self):
        # artifacts_dir is bind-mounted into Docker and may be chowned/chmodded
        # by sandbox setup. Keep host-side capture outside every container mount.
        artifacts = self._rollout_paths.artifacts_dir
        target = artifacts.parent / "jpg_capture"
        receipt = {"source": "/app/workspace/stat_ocr.xlsx", "capture_phase": "before_verifier"}
        try:
            target.mkdir(parents=True, exist_ok=True)
            await self._env.download_file(receipt["source"], target / "stat_ocr.xlsx")
            raw = (target / "stat_ocr.xlsx").read_bytes()
            receipt.update(status="exported_original_bytes", bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        except Exception as exc:
            receipt.update(status="export_failed_or_output_missing", error_type=type(exc).__name__)
        try:
            (target / "jpg_excel_export.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        except OSError:
            logging.getLogger(__name__).warning("JPG capture receipt could not be saved; verifier will still run", exc_info=True)
        rewards = await original(self)
        # Compatibility copies are best-effort, not prerequisites for scoring.
        # The unmounted sidecar remains the authoritative capture if denied.
        try:
            artifacts.mkdir(parents=True, exist_ok=True)
            for name in ("stat_ocr.xlsx", "jpg_excel_export.json"):
                if (target / name).is_file():
                    shutil.copy2(target / name, artifacts / name)
        except OSError:
            logging.getLogger(__name__).warning("JPG artifacts mirror unavailable; preserved jpg_capture sidecar")
        # Preserve rich field feedback for the normal SkillRevise diagnosis events.
        accuracy = self._rollout_paths.verifier_dir / "accuracy.json"
        try:
            if accuracy.is_file():
                report = json.loads(accuracy.read_text(encoding="utf-8"))
                (target / "field_feedback.json").write_text(json.dumps(report), encoding="utf-8")
                with (self._rollout_paths.verifier_dir / "test-stdout.txt").open("a", encoding="utf-8") as handle:
                    handle.write("\nJPG_ALLOWED_FIELD_FEEDBACK\n" + json.dumps(report, ensure_ascii=True) + "\n")
        except (OSError, ValueError):
            logging.getLogger(__name__).warning("JPG feedback mirror failed; verifier reward is unchanged", exc_info=True)
        return rewards

    Rollout.verify = verify_with_export
    Rollout._jpg_excel_export_installed = True
