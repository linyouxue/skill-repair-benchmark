"""Copy the pinned historical attempt and project feedback without claiming verified grading."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REF = "bee9b0df5b04a300735e5009f5238f5d5c8aaf61"
PREFIX = "evaluation/results/GPT52-AllTasks-RepresentativeRuns-20260916/tasks/sec-financial-report/"
RUN = "sec-financial-report-original-skill-server-r003"
KEEP = ["run_selection.json", *["selected_run/" + n for n in [
    "trajectory/acp_trajectory.jsonl", "trajectory/llm_trajectory.jsonl", "trainer/atif.json",
    "results.jsonl", "result.json", "benchmark_result.json", "executor_request.json",
    "config.json", "prompts.json", "rewards.jsonl", "timing.json", "verifier/test-stdout.txt"]]]


def native_path(name):
    return "diagnosis/" + ("source_run/" + name[len("selected_run/"):] if name.startswith("selected_run/") else name)


def project_replay(feedback, metadata, inventory, index):
    summary_path = ROOT / "validation/verifier_replay/SUMMARY.json"
    if not summary_path.exists():
        return
    replay = json.loads(summary_path.read_text(encoding="utf-8"))
    provenance = json.loads((ROOT / replay["recovered_output_provenance"]).read_text(encoding="utf-8"))
    actual = ROOT / provenance["recovered_file"]
    recovered_hash = hashlib.sha256(actual.read_bytes()).hexdigest()
    historical = next(r for r in replay["accuracy_verifier"] if r["case"] == "historical")
    assert recovered_hash == provenance["recovered_file_sha256"] == historical["answers_sha256"]
    assert replay["recovered_output_grade_verified"]
    official = next(r for r in replay["official_core"] if r["case"] == "historical")
    model_fail = replay["effective_task_outcome"] == "FAIL"
    feedback.update({"historical_tests": feedback["tests"], "tests": official["tests"],
        "tests_source": "verifier_only_replay_on_recovered_recorded_output",
        "current_accuracy": historical["accuracy"], "current_accuracy_unavailable_reason": None,
        "current_accuracy_source": historical["report"],
        "recovered_output_grade_verified": True, "accepted_as_replay_verified_model_fail": model_fail,
        "question_feedback": replay["historical_question_results"],
        "grading_limitation": "Historical verifier bootstrap failed; current FAIL and item accuracy are verified by a separate Docker replay on output recovered from recorded write/read observations. No independent historical file archive.",
        "replay_summary": "validation/verifier_replay/SUMMARY.json"})
    metadata.update({"historical_original_verifier_healthy": False,
        "recovered_output_grade_verified": True, "accepted_as_replay_verified_model_fail": model_fail,
        "effective_task_outcome": replay["effective_task_outcome"],
        "replayed_item_accuracy": historical["accuracy"],
        "recovered_output": provenance["recovered_file"],
        "recovered_output_provenance": replay["recovered_output_provenance"],
        "replay_summary": "validation/verifier_replay/SUMMARY.json"})
    inventory["files"] = [{"path": provenance["recovered_file"], "sha256": recovered_hash,
        "origin": "actual_trajectory_write_and_file_readback", "independently_archived_historical_file": False,
        "answer_values_recomputed_or_corrected": False, "provenance": replay["recovered_output_provenance"]}]
    index.update({"recovered_output": provenance["recovered_file"],
        "recovered_output_provenance": replay["recovered_output_provenance"],
        "recovered_output_grade_verified": True, "accepted_as_replay_verified_model_fail": model_fail,
        "replay_summary": "validation/verifier_replay/SUMMARY.json"})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-repo", type=Path, required=True)
    args = parser.parse_args()
    repo = args.archive_repo.resolve()
    tree = subprocess.check_output(["git", "ls-tree", "-r", REF, "--", PREFIX], cwd=repo).decode()
    blobs = {path: meta.split()[2] for meta, path in (row.split("\t", 1) for row in tree.splitlines())}

    def get(name, save=True):
        path = PREFIX + name
        expected = blobs[path]
        dest = ROOT / native_path(name)
        if save and dest.exists():
            data = dest.read_bytes()
        else:
            url = f"https://raw.githubusercontent.com/linyouxue/skill-repair-benchmark/{REF}/{path}"
            for attempt in range(2):
                try:
                    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=90) as r:
                        data = r.read()
                    break
                except Exception:
                    if attempt:
                        raise
                    time.sleep(1)
        digest = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
        if digest != expected:
            raise ValueError("Pinned source differs: " + name)
        if save:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        return name, data, expected

    with ThreadPoolExecutor(max_workers=2) as pool:
        records = list(pool.map(get, KEEP))
    saved = {name: data for name, data, _ in records}
    selection = json.loads(saved["run_selection.json"])
    benchmark = json.loads(saved["selected_run/benchmark_result.json"])
    result = json.loads(saved["selected_run/result.json"])
    if selection.get("rollout_id") != RUN or benchmark.get("execution_ok") is not True or benchmark.get("task_passed") is not False:
        raise ValueError("Not the pinned historical GPT-5.2 attempt")
    # The public archive has pytest stdout, not CTRF. Extract only test names/status.
    stdout = saved["selected_run/verifier/test-stdout.txt"]
    stdout_blob = blobs[PREFIX + "selected_run/verifier/test-stdout.txt"]
    tests = [{"name": n, "status": s.lower()} for n, s in re.findall(
        r"test_outputs\.py::([\w\[\]_.-]+)\s+(PASSED|FAILED|ERROR|SKIPPED)", stdout.decode("utf-8", errors="replace"))]
    feedback = {"original_reward": benchmark.get("reward"), "historical_task_passed": False,
                "tests": tests, "current_accuracy": None,
                "current_accuracy_unavailable_reason": "original_answers_json_not_archived",
                "test_pass_ratio_is_not_answer_accuracy": True,
                "reference_values_or_verifier_assertions_included": False,
                "source_stdout_git_blob": stdout_blob,
                "source_grade_verified": False, "accepted_as_healthy_scored_fail": False,
                "grading_limitation": "Pinned verifier failed downloading uv before pytest; the claimed replay lacks frozen-answer and log provenance."}
    metadata = {k: benchmark.get(k) for k in ["task_id", "model", "condition", "execution_ok", "reward", "task_passed",
                "agent_iterations", "provider_requests", "wall_time_sec", "cost_usd", "skill_exposure"] if k in benchmark}
    metadata.update({"run_id": RUN, "original_artifacts": "not_archived",
                     "agent_result_metadata": {k: result.get("agent_result", {}).get(k) for k in ["iterations_used", "stop_reason"]},
                     "n_skill_invocations": result.get("n_skill_invocations"),
                     "source_grade_verified": False, "accepted_as_healthy_scored_fail": False,
                     "skill_body_preloaded": True, "preloaded_skill_bodies": 2,
                     "skill_instructions_present_in_provider_responses": "30/30",
                     "audit": "validation/source_run_audit.json"})
    output = ROOT / "diagnosis/outputs"
    output.mkdir(parents=True, exist_ok=True)
    inventory = {"original_answers_json_status": "not_archived", "files": [],
                 "missing_archive_does_not_prove_no_output_was_generated": True}
    index = {"task_id": "sec-financial-report", "run_id": RUN, "source_commit": REF,
             "source_url": f"https://github.com/linyouxue/skill-repair-benchmark/tree/{REF}/{PREFIX}selected_run",
             "original_task": "task.md", "original_skills": "environment/skills",
             "native_run": "diagnosis/source_run", "allowed_feedback": "diagnosis/outputs/allowed_feedback.json",
             "files": [{"path": native_path(n), "source_path": PREFIX + n, "git_blob": blob,
                        "bytes": len(data)} for n, data, blob in records],
             "model_calls": 0, "original_run_unchanged": True,
             "source_grade_verified": False, "accepted_as_healthy_scored_fail": False,
             "historical_status_preserved": True, "audit": "validation/source_run_audit.json"}
    project_replay(feedback, metadata, inventory, index)
    for name, value in [("allowed_feedback.json", feedback), ("execution_metadata.json", metadata), ("output_inventory.json", inventory)]:
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "diagnosis/index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pinned_files": len(records), "historical_test_statuses": len(tests),
                      "replayed_test_statuses": len(feedback["tests"]) if feedback.get("recovered_output_grade_verified") else 0,
                      "model_calls": 0}))


if __name__ == "__main__":
    main()
