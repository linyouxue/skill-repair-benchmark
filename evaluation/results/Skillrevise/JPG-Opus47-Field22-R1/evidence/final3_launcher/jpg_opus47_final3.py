#!/usr/bin/env python3
"""Complete three independent final22 runs; preserve the existing first run."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import jpg_opus47_workflow as opus
from scripts import jpg_gpt55_workflow as wf


def check_run(folder, payload, frozen):
    raw = wf.read(folder / "result.json")
    request = wf.read(folder / "executor_request.json")
    policy = raw.get("executor") or raw.get("agent_result", {}).get("executor", {})
    prompts = policy.get("prompt_runs", [])
    cap_ok = policy.get("max_parent_iterations_per_step") == 65 and bool(prompts) and all(
        p.get("max_iterations") == 65 and 0 <= p.get("iterations_used", -1) <= 65 for p in prompts)
    from skillrevise.benchmarks.unified_executor_adapter import _bundle_sha256
    if (request.get("condition") != "method-skill" or request.get("model_selection", {}).get("model") != wf.MODEL
            or request.get("skill_bundle_manifest", {}).get("skill_bundle_sha256") != _bundle_sha256(frozen)):
        raise RuntimeError("Final run model/bundle identity mismatch")
    if not (payload.get("execution_ok") and cap_ok and (folder / "artifacts/stat_ocr.xlsx").is_file()
            and (folder / "verifier/accuracy.json").is_file()):
        raise RuntimeError("Final run infrastructure/evidence incomplete; retained, not automatically rerun")
    accuracy = wf.read(folder / "verifier/accuracy.json")
    if accuracy["reward"] != payload["reward"]:
        raise RuntimeError("Native result reward and accuracy differ")
    return {"rollout_id": request["rollout_id"], "reward": payload["reward"],
            "execution_ok": True, "cap65_verified": True, "directory": str(folder),
            "excel": str(folder / "artifacts/stat_ocr.xlsx"), "iterations": payload.get("agent_iterations"),
            "termination_reason": payload.get("termination_reason")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    opus.configure()
    wf.verify_prepared()
    wf.verify_code()
    submission = wf.RUN / "submission" / wf.SUBMISSION_NAME
    frozen = submission / "skills"
    files = wf.read(wf.RUN / "frozen_bundle.json")["files"]
    if wf.digest_files(frozen) != files:
        raise RuntimeError("Frozen Skill changed; refusing all repeated evaluations")
    first = wf.read(wf.RUN / "final_execution.json")
    rows = [check_run(submission / "evidence/final_run", first["result"], frozen)]
    state = wf.RUN / "final3"
    if not args.status:
        opus.guard_model()
        state.mkdir(exist_ok=True)
        plan = {"frozen_files": files, "model": wf.MODEL, "total_runs": 3,
                "first_rollout": rows[0]["rollout_id"], "provider_base_url": os.environ.get("BENCHFLOW_PROVIDER_BASE_URL")}
        if (state / "plan.json").exists() and wf.read(state / "plan.json") != plan:
            raise RuntimeError("Repeated-run configuration changed")
        wf.write(state / "plan.json", plan)
        source = state / "launcher"
        source.mkdir(exist_ok=True)
        for name in ("jpg_opus47_final3.py", "run_jpg_opus47_final3.sh"):
            p = ROOT / "scripts" / name
            out = source / name
            if out.exists() and out.read_bytes() != p.read_bytes():
                raise RuntimeError("Repeated-run launcher changed; preserve existing code provenance")
            shutil.copy2(p, out)
    executor = None
    for number in (2, 3):
        record = state / f"run_{number:02d}.json"
        if record.exists():
            saved = wf.read(record)
            rows.append(check_run(Path(saved["directory"]), saved["result"], frozen))
            print(f"Run {number}: existing result retained; no API call.", flush=True)
            continue
        if args.status:
            print(f"Run {number}: not completed")
            continue
        intent = state / f"run_{number:02d}_started.json"
        if intent.exists():
            raise RuntimeError(f"Run {number} previously started without completed export; inspect before retrying")
        if executor is None:
            from skillrevise.benchmarks.jpg_runtime import set_final_iteration_cap, install_excel_export_hook
            wf.write(state / "iteration_policy.json", set_final_iteration_cap())
            install_excel_export_hook()
            from skillrevise.benchmarks.unified_executor_adapter import build_shared_executor
            executor = build_shared_executor(tasks_root=wf.RUN / "tasks", jobs_root=wf.RUN / "final3_jobs",
                model=wf.MODEL, prebuilt_images_manifest=wf.RUN / "prebuilt_images.json")
        if wf.digest_files(frozen) != files:
            raise RuntimeError("Frozen bundle changed before execution")
        rollout = f"jpg-ocr-stat-final65-run{number}-" + uuid.uuid4().hex[:12]
        wf.write(intent, {"rollout_id": rollout, "independent_trial": number, "no_best_of_retry": True})
        print(f"Run {number}/3: starting new independent final65 Agent execution.", flush=True)
        result = executor.run(task_id="jpg-ocr-stat", method_id=wf.METHOD + "-final65",
            stage=f"final65-run{number}", rollout_id=rollout, condition="method-skill", skill_bundle=frozen)
        payload = result.to_dict()
        # Persist before export/checks, preserving even an infrastructure error.
        wf.write(state / f"run_{number:02d}_native.json", payload)
        target = submission / "evidence/final_runs" / f"run_{number:02d}"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(Path(result.artifacts.rollout_dir), target)
        capture = target / "jpg_capture/stat_ocr.xlsx"
        if capture.exists():
            (target / "artifacts").mkdir(exist_ok=True)
            shutil.copy2(capture, target / "artifacts/stat_ocr.xlsx")
        wf.write(record, {"directory": str(target), "result": payload})
        rows.append(check_run(target, payload, frozen))
        print(f"Run {number}: reward={payload['reward']}", flush=True)
    summary = {"completed": len(rows), "required": 3, "runs": rows,
               "mean_reward": sum(r["reward"] for r in rows) / 3 if len(rows) == 3 else None}
    print(json.dumps(summary, indent=2))
    if args.status:
        return
    wf.write(state / "summary.json", summary)
    wf.write(submission / "evidence/final3_summary.json", summary)
    shutil.copytree(source, submission / "evidence/final3_launcher", dirs_exist_ok=True)
    readme = submission / "README.md"
    marker = "\n## Three independent original22 final executions\n"
    text = readme.read_text().split(marker)[0] + marker
    text += "Same frozen Skill, same Opus route, each capped at 65 parent iterations. All results retained.\n\n"
    text += "| Run | Field accuracy | Run ID |\n|---|---:|---|\n"
    for i, row in enumerate(rows, 1):
        text += f"| {i} | {row['reward']:.8f} | {row['rollout_id']} |\n"
    text += f"\nArithmetic mean: {summary['mean_reward']:.8f}.\n"
    text += "Run 1: evidence/final_run/; runs 2/3: evidence/final_runs/run_02/ and run_03/. Each contains native Excel, trajectory, scoring and execution metadata. Generalization not run.\n"
    readme.write_text(text)
    print("DONE: three independent original22 final executions complete; no Skill modifications.")


if __name__ == "__main__":
    main()
