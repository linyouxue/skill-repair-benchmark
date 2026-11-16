#!/usr/bin/env python3
"""Independent pure-Opus JPG experiment; reuse environments, never GPT outputs."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import uuid
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import jpg_gpt55_workflow as workflow

SOURCE = ROOT / "runs/jpg-gpt55-field22-r1"


def configure():
    workflow.RUN = ROOT / "runs/jpg-opus47-field22-r1"
    workflow.MODEL = "tatu-anthropic/claude-opus-4-7"
    workflow.DIAGNOSIS_MODEL = "claude-opus-4-7"
    workflow.MODEL_LABEL = "Claude Opus 4.7"
    workflow.METHOD = "skillrevise-jpg-opus47-field22-r1"
    workflow.IMAGE = "skillrevise-jpg-field22-opus47:v1"
    workflow.SUBMISSION_NAME = "skillrevise__opus47-field22-r1"
    workflow.EXTRA_SNAPSHOT_FILES = ("scripts/jpg_opus47_workflow.py", "scripts/run_jpg_opus47_stage.sh")


def prepare():
    """Copy only the validated model-independent task, not prior model records."""
    run = workflow.RUN
    if (run / "prepared.json").is_file():
        workflow.verify_prepared()
        workflow.verify_code()
        print("Opus preparation already complete; unchanged.")
        return
    if run.exists():
        raise RuntimeError("Incomplete Opus run directory exists; retain it for inspection")
    state = workflow.read(SOURCE / "prepared.json")
    source_task = SOURCE / "tasks/jpg-ocr-stat"
    if state["source_commit"] != workflow.COMMIT or workflow.digest_files(source_task) != state["task_files"]:
        raise RuntimeError("Original prepared task changed; refusing environment reuse")
    manifest = workflow.read(workflow.PACKAGE / "source_manifest.json")
    if manifest["commit"] != workflow.COMMIT:
        raise RuntimeError("Source package commit mismatch")
    import hashlib
    for row in manifest["files"]:
        if hashlib.sha256((workflow.PACKAGE / row["path"]).read_bytes()).hexdigest() != row["sha256"]:
            raise RuntimeError("Source package changed: " + row["path"])
    shutil.copytree(source_task, run / "tasks/jpg-ocr-stat")
    for name in ("manifest.json", "original_workbook_field_rescore.json"):
        shutil.copy2(SOURCE / name, run / name)
    shutil.copytree(SOURCE / "source_snapshot", run / "source_snapshot")
    state.update(experiment_model=workflow.MODEL, model_outputs_reused=False,
                 environment_copied_from=str(source_task), package=str(workflow.PACKAGE))
    workflow.write(run / "prepared.json", state)
    workflow.snapshot_code()
    print("Prepared independent Opus experiment. Reused task/verifier only; no GPT diagnoses, probes or model responses copied.")


def settings():
    return {"provider": "anthropic", "model": "claude-opus-4-7", "effort": "high",
            "thinking": "disabled", "temperature": 1.0, "max_tokens": 32768,
            "base_url": os.environ.get("SKILL_REVISE_REVISION_LLM_BASE_URL"),
            "rollout_model": workflow.MODEL, "candidate_iteration_cap": 60,
            "final_iteration_cap": 65, "command_attempts": 1, "http_attempts": 1,
            "heldout_images_used": False, "gpt_model_outputs_reused": False}


def guard_model():
    from skillrevise.llm.command import load_config
    config = load_config(os.environ)
    if (config.provider, config.model, config.effort, config.thinking_mode, config.max_tokens, config.temperature) != (
            "anthropic", "claude-opus-4-7", "high", "disabled", 32768, 1.0):
        raise RuntimeError("Pure Opus configuration mismatch; use scripts/run_jpg_opus47_stage.sh")
    if os.environ.get("BENCHMARK_MODEL") != workflow.MODEL or os.environ.get("BENCHMARK_REASONING_EFFORT"):
        raise RuntimeError("Wrong rollout model or unsupported ACP effort override")
    workflow.write(workflow.RUN / "evidence/opus_configuration.json", settings())


def probe_signature(images):
    return {"settings": settings(), "source_commit": workflow.COMMIT,
            "images": [{"asset_id": row["asset_id"], "sha256": row["sha256"]} for row in images]}


def build():
    workflow.verify_prepared()
    if not (workflow.RUN / "probe_passed.json").is_file():
        raise RuntimeError("Pass Opus image probe before building")
    if (workflow.RUN / "prebuilt_images.json").exists():
        workflow.build()
        return
    workflow.call("bash", ROOT / "scripts/bootstrap_unified_openhands_runtime_cache.sh")
    workflow.call("bash", ROOT / "scripts/patch_unified_egress_firewall_cap.sh")
    from benchflow._utils.task_authoring import task_digest
    source_manifest = SOURCE / "prebuilt_images.json"
    if source_manifest.is_file():
        manifest = workflow.read(source_manifest)
        item = manifest["tasks"]["jpg-ocr-stat"]
        inspected = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", item["image"]],
                                   capture_output=True, text=True)
        if (inspected.returncode == 0 and inspected.stdout.strip() == item["image_id"]
                and item["task_digest"] == task_digest(workflow.RUN / "tasks/jpg-ocr-stat")):
            workflow.write(workflow.RUN / "prebuilt_images.json", manifest)
            workflow.write(workflow.RUN / "evidence/environment_reuse.json", {
                "source_manifest": str(source_manifest), "image_id": item["image_id"],
                "task_digest_verified": True, "model_outputs_reused": False})
            print("Reused identical JPG environment image after task digest and Docker image-ID verification; no build needed.")
            return
    workflow.build()


def prepare_export_recovery():
    """Archive only the known unscored capture-permission failure, never a valid run."""
    run = workflow.RUN
    workflow.verify_prepared()
    report = run / "skillrevise_bundle.json"
    marker = run / "evidence/export_permission_recovery.json"
    if marker.exists():
        workflow.verify_code()
        print("Export recovery already prepared; original failure remains archived.")
        return
    data = workflow.read(report)
    rows = data.get("bundle_results", [])
    if len(rows) != 1 or rows[0]["task"]["task_id"] != "jpg-ocr-stat":
        raise RuntimeError("Recovery only supports the single JPG failure")
    episodes = rows[0].get("episodes", [])
    if len(episodes) != 1 or rows[0].get("selected_overrides"):
        raise RuntimeError("Refusing to replace an experiment with accepted revisions or multiple branches")
    iterations = episodes[0]["result"]["iterations"]
    trace = iterations[-1]["evaluation"]["with_skill"]
    encoded = str(trace)
    if (len(iterations) != 2 or not iterations[0].get("revision")
            or trace.get("status") != "infrastructure_error"
            or trace.get("metadata", {}).get("reward") is not None
            or "Permission denied" not in encoded or "jpg_excel_export.json" not in encoded):
        raise RuntimeError("Not the known unscored JPG export failure; do not overwrite this report")
    old_hashes = workflow.read(run / "evidence/code_sha256.json")
    changed = [name for name, value in old_hashes.items()
               if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != value]
    allowed = {"skillrevise/benchmarks/jpg_runtime.py", "skillrevise/llm/client.py",
               "scripts/jpg_gpt55_workflow.py", "scripts/jpg_opus47_workflow.py", "scripts/run_jpg_opus47_stage.sh"}
    if set(changed) - allowed:
        raise RuntimeError("Unrelated code changed; refusing automatic recovery: " + str(changed))
    history = run / "recovery_history" / ("export-permission-" + uuid.uuid4().hex)
    # Resolve both ends before recoverable moves; neither may escape this run.
    if not history.resolve().is_relative_to(run.resolve()):
        raise RuntimeError("Recovery archive escapes experiment directory")
    history.mkdir(parents=True)
    for name in ("skillrevise_bundle.json", "skillrevise_summary.json"):
        source = run / name
        if source.exists():
            shutil.move(str(source), str(history / name))
    shutil.move(str(run / "evidence/code"), str(history / "code"))
    shutil.move(str(run / "evidence/code_sha256.json"), str(history / "code_sha256.json"))
    workflow.snapshot_code()
    workflow.verify_code()
    workflow.write(marker, {"archive": str(history), "changed_files": changed,
        "failed_candidate_run": trace["run_id"], "reason": "host capture receipt permission failure before verifier",
        "old_rollouts_preserved": True, "existing_model_responses_preserved": True,
        "score_or_verifier_semantics_changed": False, "automatic_model_calls": False})
    print("Archived unscored report and original code:", history)
    print("Repair can now reuse existing model responses and replay the unscored candidate.")


def recover_export():
    prepare_export_recovery()
    workflow.repair()


def prepare_resume():
    workflow.verify_prepared()
    marker = workflow.RUN / "evidence/candidate_resume_enabled.json"
    hashes = workflow.read(workflow.RUN / "evidence/code_sha256.json")
    changed = [name for name, value in hashes.items()
               if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != value]
    if marker.exists() and not changed:
        workflow.verify_code()
        return
    if set(changed) - {"scripts/jpg_opus47_workflow.py", "scripts/run_jpg_opus47_stage.sh", "skillrevise/method/diagnosis.py"}:
        raise RuntimeError("Unrelated changes prevent candidate resume registration: " + str(changed))
    archive = workflow.RUN / "evidence/code_history" / ("candidate-resume-" + uuid.uuid4().hex)
    if not archive.resolve().is_relative_to(workflow.RUN.resolve()):
        raise RuntimeError("Code archive escapes experiment")
    archive.mkdir(parents=True)
    if marker.exists():
        shutil.copy2(marker, archive / "previous_resume_marker.json")
    shutil.move(str(workflow.RUN / "evidence/code"), str(archive / "code"))
    shutil.move(str(workflow.RUN / "evidence/code_sha256.json"), str(archive / "code_sha256.json"))
    workflow.snapshot_code()
    workflow.verify_code()
    workflow.write(marker, {"code_archive": str(archive), "changed_files": changed,
        "reason": "resume after provider 400 without repeating valid candidate execution",
        "thinking_unchanged": "disabled", "automatic_api_calls": False})
    print("Candidate execution checkpoints enabled; existing scores and model settings unchanged.")


def resume_repair():
    prepare_resume()
    from skillrevise.benchmarks.jpg_resume import install_candidate_resume
    install_candidate_resume(workflow.RUN, model=workflow.MODEL, method_id=workflow.METHOD)
    workflow.repair()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "probe", "build", "repair", "final", "status", "selfcheck", "prepare_export_recovery", "recover_export", "prepare_resume", "resume_repair"))
    stage = parser.parse_args().stage
    configure()
    workflow.probe_signature = probe_signature
    os.chdir(ROOT)
    if stage in {"probe", "repair", "final", "recover_export", "resume_repair"}:
        workflow.verify_prepared()
        if stage not in {"recover_export", "resume_repair"}:
            workflow.verify_code()
        guard_model()
        if stage in {"repair", "final", "recover_export", "resume_repair"}:
            from skillrevise.benchmarks.jpg_diagnosis import image_blocks
            images = image_blocks(workflow.PACKAGE)[1]
            if not workflow.checkpoint_matches(workflow.RUN / "probe_passed.json", probe_signature(images)):
                raise RuntimeError("Successful matching Opus probe required")
    if stage == "prepare":
        prepare()
    elif stage == "build":
        build()
    elif stage == "prepare_export_recovery":
        prepare_export_recovery()
    elif stage == "recover_export":
        recover_export()
    elif stage == "prepare_resume":
        prepare_resume()
    elif stage == "resume_repair":
        resume_repair()
    else:
        getattr(workflow, stage)()


if __name__ == "__main__":
    main()
