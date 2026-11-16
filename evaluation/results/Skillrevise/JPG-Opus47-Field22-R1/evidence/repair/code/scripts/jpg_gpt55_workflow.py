#!/usr/bin/env python3
"""User-run stages for the GPT-5.5 JPG field-accuracy experiment."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
RUN = ROOT / "runs/jpg-gpt55-field22-r1"
PACKAGE = Path(os.environ.get("SKILL_REVISE_JPG_DIAGNOSIS_PACKAGE",
                   "/mnt/d/project/skillrevise-handoff-experiments/data/jpg-field-accuracy-diagnosis-20261022"))
COMMIT = "64e7ca807b19b8e3c19e96853a50f175e6dbdb19"
MODEL = "vllm/gpt-5.5"
METHOD = "skillrevise-jpg-gpt55-field22-r1"
IMAGE = "skillrevise-jpg-field22-gpt55:v1"
DIAGNOSIS_MODEL = "gpt-5.5"
MODEL_LABEL = "GPT-5.5"
SUBMISSION_NAME = "skillrevise__gpt55-field22-r1"
EXTRA_SNAPSHOT_FILES = ()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def call(*argv):
    print("Running:", " ".join(map(str, argv)), flush=True)
    subprocess.run(list(map(str, argv)), cwd=ROOT, check=True)


def digest_files(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(root).rglob("*")) if p.is_file()}


def validate_bundle(original, candidate):
    old, new = digest_files(original), digest_files(candidate)
    if set(old) != set(new):
        raise RuntimeError("Candidate does not preserve the full original five-Skill bundle")
    allowed = {f"{name}/SKILL.md" for name in ("image-ocr", "openai-vision", "pdf", "video-frame-extraction", "xlsx")}
    changed = [path for path in old if old[path] != new[path]]
    if any(path not in allowed for path in changed):
        raise RuntimeError("Only the five existing SKILL.md files may change")
    return changed


def prepare():
    from fetch_jpg_diagnosis_package import fetch
    source = read(PACKAGE / "source_manifest.json")
    if source["commit"] != COMMIT:
        raise RuntimeError("Diagnosis package commit differs from the pinned experiment")
    for item in source["files"]:
        if hashlib.sha256((PACKAGE / item["path"]).read_bytes()).hexdigest() != item["sha256"]:
            raise RuntimeError("Diagnosis source file differs: " + item["path"])
    target = RUN / "tasks/jpg-ocr-stat"
    if (RUN / "prepared.json").is_file():
        verify_prepared()
        print("Preparation already complete and unchanged; skipped.")
        return
    if target.exists():
        raise RuntimeError("Incomplete preparation exists; retain it and use a fresh run label before retrying")
    target.mkdir(parents=True)
    shutil.copy2(PACKAGE / "task.md", target / "task.md")
    shutil.copytree(PACKAGE / "environment", target / "environment")
    api = "https://api.github.com/repos/linyouxue/skill-repair-benchmark"
    top = json.loads(fetch(f"{api}/git/trees/{COMMIT}"))
    task_sha = next(row["sha"] for row in top["tree"] if row["path"] == "jpg-ocr-stat")
    tree = json.loads(fetch(f"{api}/git/trees/{task_sha}?recursive=1"))
    if tree.get("truncated"):
        raise RuntimeError("Task tree truncated")
    verifier_manifest = []
    for entry in tree["tree"]:
        if entry["type"] != "blob" or not entry["path"].startswith("verifier/"):
            continue
        raw = fetch(f"https://raw.githubusercontent.com/linyouxue/skill-repair-benchmark/{COMMIT}/jpg-ocr-stat/{entry['path']}")
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if blob != entry["sha"]:
            raise RuntimeError("Verifier source Git hash mismatch")
        path = target / entry["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        verifier_manifest.append({"path": entry["path"], "git_blob": blob})
    # Archive the unmodified online installer, then use the same pinned pytest
    # and scoring code offline from a venv warmed during docker build.
    (RUN / "source_snapshot").mkdir(parents=True, exist_ok=True)
    shutil.copy2(target / "verifier/test.sh", RUN / "source_snapshot/original_test.sh")
    shutil.copy2(target / "environment/Dockerfile", RUN / "source_snapshot/original_Dockerfile")
    with (target / "environment/Dockerfile").open("a", encoding="utf-8") as handle:
        handle.write("\n# Local reproducible verifier dependency warmup; scoring code unchanged.\n"
                     "RUN apt-get update && apt-get install -y --no-install-recommends python3-venv "
                     "&& python3 -m venv /opt/jpg-verifier "
                     "&& /opt/jpg-verifier/bin/pip install --no-cache-dir pytest==8.4.1 pytest-json-ctrf==0.3.5 openpyxl==3.1.5\n")
    (target / "verifier/test.sh").write_text(
        "#!/bin/bash\nset -euo pipefail\nmkdir -p /logs/verifier\n"
        "rm -f /logs/verifier/reward.txt /logs/verifier/reward.json /logs/verifier/ctrf.json /logs/verifier/accuracy.json\n"
        "status=0\n/opt/jpg-verifier/bin/python -m pytest --ctrf /logs/verifier/ctrf.json /verifier/test_outputs.py -rA --tb=short || status=$?\n"
        "if [ \"$status\" -ne 0 ] && [ \"$status\" -ne 1 ]; then exit \"$status\"; fi\n"
        "/opt/jpg-verifier/bin/python /verifier/write_reward.py\n", encoding="utf-8")
    (target / "verifier/test.sh").chmod(0o755)
    # Local scoring sees the frozen reference only inside this scoring process.
    call(sys.executable, target / "verifier/score_accuracy.py", "--actual", PACKAGE / "diagnosis/outputs/stat_ocr.xlsx",
         "--report", RUN / "original_workbook_field_rescore.json")
    score = read(RUN / "original_workbook_field_rescore.json")
    if score["reward"] != read(PACKAGE / "diagnosis/outputs/allowed_feedback.json")["reward"]:
        raise RuntimeError("Frozen original workbook re-score differs from published feedback")
    write(RUN / "manifest.json", {"tasks": [{"task_id": "jpg-ocr-stat", "family": "receipt-ocr",
        "instruction": (PACKAGE / "diagnosis/task_prompt.md").read_text(encoding="utf-8"),
        "acceptance_criteria": ["field_accuracy=(date_correct+amount_correct)/44; delivery status separately reported"]}]})
    write(RUN / "prepared.json", {"source_commit": COMMIT, "package": str(PACKAGE),
        "verifier_source": verifier_manifest, "task_files": digest_files(target),
        "local_changes": ["offline verifier dependency installation only", "separate Docker tag; original 39 image tags retained"],
        "scoring_semantics_changed_locally": False, "original_native_reward": 0,
        "offline_regraded_reward": score["reward"], "heldout_data_used": False})
    snapshot_code()
    print(f"Prepared one JPG task; original workbook field reward={score['reward']}; no model calls.")


def verify_prepared():
    state = read(RUN / "prepared.json")
    if state["source_commit"] != COMMIT or digest_files(RUN / "tasks/jpg-ocr-stat") != state["task_files"]:
        raise RuntimeError("Prepared task changed; do not reuse this run's image/results")


def snapshot_code():
    snapshot = RUN / "evidence/code"
    for relative in ("skillrevise", "scripts/jpg_gpt55_workflow.py", "scripts/run_jpg_gpt55_stage.sh", "scripts/fetch_jpg_diagnosis_package.py", *EXTRA_SNAPSHOT_FILES):
        source = ROOT / relative
        dest = snapshot / relative
        if source.is_dir():
            shutil.copytree(source, dest, ignore=shutil.ignore_patterns("__pycache__", "local_llm_config.py"))
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
    write(RUN / "evidence/code_sha256.json", digest_files(snapshot))


def verify_code():
    hashes = read(RUN / "evidence/code_sha256.json")
    for relative, expected in hashes.items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
            raise RuntimeError("Experiment code changed since prepare: " + relative)


def refresh_code():
    """Archive a pre-repair launcher-only change without losing the prepared snapshot."""
    hashes = read(RUN / "evidence/code_sha256.json")
    changed = [name for name, value in hashes.items()
               if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != value]
    if not changed:
        print("Code snapshot already matches; nothing to update.")
        return
    if (RUN / "skillrevise_bundle.json").exists() or (RUN / "jobs").exists():
        raise RuntimeError("Repair may already have started; retain its original code snapshot")
    request_root = RUN / "evidence/repair_requests"
    if request_root.exists() and any(path.is_dir() and not path.name.startswith(("skill_diagnosis-", "bundle_skill_selection-"))
                                     and path.name != "resume_receipts" for path in request_root.iterdir()):
        raise RuntimeError("Requests beyond initial diagnosis exist; do not refresh this snapshot")
    if set(changed) - {"scripts/jpg_gpt55_workflow.py", "scripts/run_jpg_gpt55_stage.sh",
                       "skillrevise/llm/client.py", "skillrevise/method/diagnosis.py",
                       "skillrevise/benchmarks/jpg_diagnosis.py"}:
        raise RuntimeError("Only pre-repair launcher fixes may refresh this snapshot: " + str(changed))
    history = RUN / "evidence/code_history" / uuid.uuid4().hex
    history.mkdir(parents=True)
    shutil.move(str(RUN / "evidence/code"), str(history / "code"))
    shutil.move(str(RUN / "evidence/code_sha256.json"), str(history / "code_sha256.json"))
    write(history / "change.json", {"reason": "JPG upstream 502/503 recovery: preserve successful RELATED_RECORDS serialization order for exact request reuse; no input reduction or automatic retry",
                                    "changed_files": changed, "original_snapshot_preserved": True})
    snapshot_code()
    verify_code()
    print("Pre-repair launcher snapshot refreshed; original snapshot preserved at", history)


def probe_signature(images):
    return {"model": DIAGNOSIS_MODEL, "base_url": os.environ.get("SKILL_REVISE_REVISION_LLM_BASE_URL"),
            "source_commit": COMMIT, "images": [{"asset_id": i["asset_id"], "sha256": i["sha256"]} for i in images]}


def checkpoint_matches(path, signature):
    path = Path(path)
    if not path.exists():
        return False
    if read(path).get("signature") != signature:
        raise RuntimeError(f"Existing probe settings differ: {path}; retain the record and use a fresh experiment")
    return True


def send_probe(client, prompt, purpose, image_count):
    record = RUN / "evidence/probe_attempts" / f"{purpose}-{uuid.uuid4().hex}.json"
    started = time.monotonic()
    info = {"purpose": purpose, "image_blocks": image_count, "status": "starting",
            "payload_json_bytes": len(json.dumps(prompt.messages).encode("utf-8"))}
    write(record, info)
    print(f"[Probe] {purpose}: sending {image_count} image block(s), about {info['payload_json_bytes'] / 1024 / 1024:.2f} MiB; one attempt.", flush=True)
    try:
        reply = client.complete(prompt, purpose=purpose)
    except Exception as exc:
        info.update(status="failed", error_type=type(exc).__name__, elapsed_seconds=time.monotonic() - started)
        write(record, info)
        print(f"[Probe] Failed after {info['elapsed_seconds']:.1f}s; original HTTP evidence retained; no automatic retry.", flush=True)
        raise
    info.update(status="response_received", elapsed_seconds=time.monotonic() - started,
                request_evidence_dir=reply.metadata.get("request_evidence_dir"))
    write(record, info)
    return reply


def probe():
    from skillrevise.benchmarks.jpg_diagnosis import image_blocks, task_prompt, configure_task
    from skillrevise.core.models import TaskSpec
    from skillrevise.llm.client import CommandLLMClient
    from skillrevise.llm.multimodal import MultimodalPrompt
    verify_prepared()
    blocks, images = image_blocks(PACKAGE)
    signature = probe_signature(images)
    if checkpoint_matches(RUN / "probe_passed.json", signature):
        print("Existing successful probe found; skipped paid calls.")
        return
    client = CommandLLMClient([sys.executable, "-m", "skillrevise.llm.command"], timeout_seconds=1200)
    vision_checkpoint = RUN / "probe_vision_passed.json"
    if checkpoint_matches(vision_checkpoint, signature):
        vision_metadata = read(vision_checkpoint)["request"]
        print("[Probe 1/2] Existing matching single-image vision probe passed; skipping paid call.", flush=True)
    else:
        first = next(i for i, image in enumerate(images) if image["asset_id"] == "007.jpg")
        content = [{"type": "text", "text": "From this original receipt image 007.jpg, extract its receipt date YYYY-MM-DD and total_amount as a two-decimal string. Return only JSON with date,total_amount. No tools."}, blocks[first]]
        response = send_probe(client, MultimodalPrompt([{"role": "user", "content": content}],
                str(RUN / "evidence/probe"), {"stage": "single_image_connectivity_only", "image": images[first]}),
                "jpg_single_image_vision_probe", 1)
        parsed = parse_json(response.text)
        known = next(row for row in read(PACKAGE / "diagnosis/outputs/predictions.json")["rows"] if row["filename"] == "007.jpg")
        feedback = next(row for row in read(PACKAGE / "diagnosis/outputs/allowed_feedback.json")["field_feedback"] if row["filename"] == "007.jpg")
        if not (feedback["date_correct"] and feedback["amount_correct"] and
                all(parsed.get(key) == known[key] for key in ("date", "total_amount"))):
            raise RuntimeError("Visual extraction probe mismatch; inspect evidence/probe before running repair")
        vision_metadata = response.metadata
        write(vision_checkpoint, {"signature": signature, "source_images_in_this_request": 1, "request": vision_metadata})
        print("[Probe 1/2] Single-image visual extraction passed and checkpoint saved.", flush=True)
    # A second call tests the largest published window's real text+22-image shape.
    index = read(PACKAGE / "diagnosis/index.json")
    task = configure_task(TaskSpec("jpg-ocr-stat", "receipt-ocr", "", []), PACKAGE, RUN / "evidence/probe")
    from skillrevise.method.diagnosis import LLMDiagnoser
    from skillrevise.core.models import Skill
    from skillrevise.core.runner import PairedRunner
    from skillrevise.benchmarks.jpg_diagnosis import initial_trace_from_package
    skill = Skill("probe", "Probe only", "probe", [], [], metadata={
        "raw_markdown": (PACKAGE / "environment/skills/image-ocr/SKILL.md").read_text(encoding="utf-8")})
    runner = PairedRunner(None, paper_protocol=True)
    evaluation = runner.evaluation_from_existing_with_skill_trace(task, skill, initial_trace_from_package(PACKAGE))
    text = LLMDiagnoser(client)._build_prompt(task, skill, evaluation)
    largest, largest_prompt, largest_size = None, None, -1
    for item in index["windows"]:
        candidate_prompt = task_prompt(task, text, window_id=item["window_id"])
        size = sum(len(block.get("text", "")) for message in candidate_prompt.messages for block in message["content"])
        if size > largest_size:
            largest, largest_prompt, largest_size = item["window_id"], candidate_prompt, size
    print(f"[Probe 2/2] Full window {largest} with all 22 original images; no truncation.", flush=True)
    context_reply = send_probe(client, largest_prompt, "jpg_full_window_probe", 22)
    LLMDiagnoser(client)._parse_report(parse_json(context_reply.text))
    write(RUN / "probe_passed.json", {"signature": signature, "model": DIAGNOSIS_MODEL, "vision_probe_matched_allowed_prediction": True,
        "full_window_tested": largest, "source_images": 22, "heldout_images_used": False,
        "calls": [vision_metadata, context_reply.metadata]})
    print(f"PASS: real {MODEL_LABEL} image extraction and full-window multimodal diagnosis request.")


def parse_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(text)


def build():
    verify_prepared()
    if not (RUN / "probe_passed.json").is_file():
        raise RuntimeError("Run probe successfully before building")
    from benchflow._utils.task_authoring import task_digest
    if (RUN / "prebuilt_images.json").exists():
        print("Existing prebuilt manifest; run-time executor will verify digest and image identity.")
        return
    call("bash", ROOT / "scripts/bootstrap_unified_openhands_runtime_cache.sh")
    call("bash", ROOT / "scripts/patch_unified_egress_firewall_cap.sh")
    call("docker", "build", "-t", IMAGE, RUN / "tasks/jpg-ocr-stat/environment")
    image_id = subprocess.check_output(["docker", "image", "inspect", "--format", "{{.Id}}", IMAGE], text=True).strip()
    write(RUN / "prebuilt_images.json", {"schema_version": 1, "tasks": {"jpg-ocr-stat": {
        "image": IMAGE, "image_id": image_id, "task_digest": task_digest(RUN / "tasks/jpg-ocr-stat")}}})
    print("Image ready; one build attempt; no agent/model calls.")


def repair():
    verify_prepared()
    verify_code()
    if not (RUN / "probe_passed.json").is_file():
        raise RuntimeError("Successful probe is required")
    if (RUN / "skillrevise_bundle.json").exists():
        print("Existing repair result found; skipped paid execution.")
        return
    from skillrevise.benchmarks.jpg_runtime import install_excel_export_hook
    install_excel_export_hook()
    from skillrevise.cli import main as cli_main
    os.environ["SKILL_REVISE_JPG_EVIDENCE_ROOT"] = str(RUN / "evidence/repair_requests")
    sys.argv = ["skillrevise", str(RUN / "manifest.json"), "--manifest-kind", "skillsbench",
        "--unified-tasks-root", str(RUN / "tasks"), "--unified-jobs-root", str(RUN / "jobs"),
        "--unified-candidates-root", str(RUN / "candidates"), "--unified-model", MODEL,
        "--unified-method-id", METHOD, "--unified-prebuilt-images", str(RUN / "prebuilt_images.json"),
        "--unified-skill-bundle-mode", "replace-original", "--unified-bundle-repair",
        "--unified-bundle-initial-traces", str(PACKAGE), "--unified-bundle-max-targets", "3",
        "--unified-bundle-accept-non-degrading", "--paper-protocol", "--author-mode", "template",
        "--diagnosis-mode", "llm", "--revision-mode", "llm-principle-bank", "--principle-retrieval", "bm25",
        "--max-revisions", "3", "--llm-command", f"{sys.executable} -m skillrevise.llm.command", "--llm-timeout", "1260", "--strict-llm",
        "--output", str(RUN / "skillrevise_bundle.json"), "--summary-output", str(RUN / "skillrevise_summary.json")]
    write(RUN / "evidence/repair_command.json", {"argv": sys.argv, "model": MODEL,
        "diagnosis_model": DIAGNOSIS_MODEL, "initial_trace": "published Opus trajectory + offline original workbook field reward",
        "principle_retrieval": "bm25", "candidate_rollout_cap": 60,
        "max_revision_model_output_tokens": os.environ.get("SKILL_REVISE_REVISION_LLM_MAX_TOKENS")})
    cli_main()


def final():
    verify_prepared()
    verify_code()
    data = read(RUN / "skillrevise_bundle.json")
    rows = data["bundle_results"]
    if len(rows) != 1 or rows[0]["task"]["task_id"] != "jpg-ocr-stat":
        raise RuntimeError("Expected one JPG repair result")
    submission = RUN / "submission" / SUBMISSION_NAME
    frozen = submission / "skills"
    original = RUN / "tasks/jpg-ocr-stat/environment/skills"
    selected = ((rows[0].get("selected_trace") or {}).get("metadata") or {}).get("candidate_bundle", {}).get("root")
    bundle = Path(selected) if selected else original
    validate_bundle(original, bundle)
    if not frozen.exists():
        frozen.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(bundle, frozen)
        write(RUN / "frozen_bundle.json", {"source": str(bundle), "files": digest_files(frozen),
              "changed_skill_documents": validate_bundle(original, frozen), "selection": rows[0].get("selection"),
              "selected_overrides": rows[0].get("selected_overrides"), "heldout_data_used": False})
    if digest_files(frozen) != read(RUN / "frozen_bundle.json")["files"]:
        raise RuntimeError("Frozen bundle changed")
    if (RUN / "final_execution.json").exists():
        print("Existing final execution recorded; skipped. Inspect report; no automatic best-of reruns.")
        return
    from skillrevise.benchmarks.jpg_runtime import set_final_iteration_cap, install_excel_export_hook
    override = set_final_iteration_cap()
    install_excel_export_hook()
    write(RUN / "evidence/final_65_iteration_override.json", override)
    from skillrevise.benchmarks.unified_executor_adapter import build_shared_executor
    executor = build_shared_executor(tasks_root=RUN / "tasks", jobs_root=RUN / "final_jobs", model=MODEL,
                                      prebuilt_images_manifest=RUN / "prebuilt_images.json")
    rollout = "jpg-ocr-stat-final65-" + uuid.uuid4().hex[:12]
    result = executor.run(task_id="jpg-ocr-stat", method_id=METHOD + "-final65", stage="final65",
                          rollout_id=rollout, condition="method-skill", skill_bundle=frozen)
    payload = result.to_dict()
    write(RUN / "final_execution.json", {"rollout_id": rollout, "result": payload})
    run_dir = Path(result.artifacts.rollout_dir)
    target = submission / "evidence/final_run"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(run_dir, target)
    # Host-side capture is deliberately outside Docker's artifacts bind mount.
    captured = target / "jpg_capture/stat_ocr.xlsx"
    if captured.is_file():
        (target / "artifacts").mkdir(parents=True, exist_ok=True)
        shutil.copy2(captured, target / "artifacts/stat_ocr.xlsx")
    raw = read(target / "result.json")
    policy = raw.get("executor") or raw.get("agent_result", {}).get("executor", {})
    prompt_runs = policy.get("prompt_runs", [])
    cap_ok = policy.get("max_parent_iterations_per_step") == 65 and bool(prompt_runs) and all(
        item.get("max_iterations") == 65 and 0 <= item.get("iterations_used", -1) <= 65 for item in prompt_runs)
    field_report = target / "verifier/accuracy.json"
    xlsx = target / "artifacts/stat_ocr.xlsx"
    checks = {"execution_ok": payload.get("execution_ok"), "task_passed": payload.get("task_passed"),
              "reward": payload.get("reward"), "actual_cap_65_verified": cap_ok,
              "excel_present": xlsx.is_file(), "accuracy_report_present": field_report.is_file(),
              "frozen_bundle_files": digest_files(frozen), "final_run": str(target)}
    write(RUN / "final_checks.json", checks)
    # Publish process evidence without answers or the task verifier directory.
    evidence = submission / "evidence/repair"
    shutil.copytree(RUN / "evidence", evidence)
    for name in ("skillrevise_bundle.json", "skillrevise_summary.json", "frozen_bundle.json", "final_checks.json"):
        shutil.copy2(RUN / name, evidence / name)
    (submission / "README.md").write_text(
        f"# SkillRevise / {MODEL_LABEL} field22 r1\n\nFinal bundle frozen before any generalization access.\n"
        f"Source materials: {COMMIT}/jpg-ocr-stat/diagnosis; source Opus run retained as historical evidence.\n"
        f"Diagnosis/revision model: {DIAGNOSIS_MODEL}; final Agent: {MODEL}; original SkillRevise top3/3 revisions, BM25.\n"
        f"Final rollout: {rollout}; cap check={cap_ok}; configuration and actual records: evidence/repair/final_65_iteration_override.json and evidence/final_run/result.json.\n"
        f"Actual Excel: evidence/final_run/artifacts/stat_ocr.xlsx. Reward={payload.get('reward')}; task_passed={payload.get('task_passed')}.\n"
        "See evidence/repair for real prompts, image blocks, revisions and frozen-file hashes.\n"
        "Human involvement: adapter/runtime integration only; no manual Skill edits in this workflow.\n"
        "Generalization has not been run. Missing artifacts/infra errors remain reported in final_checks.json.\n", encoding="utf-8")
    print(json.dumps(checks, ensure_ascii=True, indent=2))
    if not (payload.get("execution_ok") and cap_ok and xlsx.is_file() and field_report.is_file()):
        raise RuntimeError("Final execution evidence incomplete; inspect final_checks.json. No automatic rerun.")
    print(f"Completed final execution (correctness may pass or fail). Submission: {submission}")


def status():
    for name in ("prepared.json", "probe_vision_passed.json", "probe_passed.json", "prebuilt_images.json", "skillrevise_bundle.json", "final_checks.json"):
        path = RUN / name
        print(f"{name}: {'present' if path.is_file() else 'not yet completed'}")
    if (RUN / "final_checks.json").exists():
        print(json.dumps(read(RUN / "final_checks.json"), indent=2))


def selfcheck():
    from skillrevise.benchmarks.jpg_runtime import set_final_iteration_cap
    print(json.dumps(set_final_iteration_cap(), indent=2))
    print("Process-only policy check passed; no Docker run and no model calls.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "probe", "build", "repair", "final", "status", "selfcheck", "refresh_code"))
    stage = parser.parse_args().stage
    os.chdir(ROOT)
    globals()[stage]()


if __name__ == "__main__":
    main()
