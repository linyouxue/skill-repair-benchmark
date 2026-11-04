"""Verifier-only Docker checks on recovered historical output and independently computed answers."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "validation/verifier_replay"


def write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob(path):
    content = path.read_bytes()
    return hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()


def run(image, label, mounts, command, allowed_codes=(0,)):
    output = BASE / label
    output.mkdir(parents=True, exist_ok=True)
    args = ["docker", "run", "--rm", "--network", "none", "--env", "PYTHONDONTWRITEBYTECODE=1"]
    for source, target in [*mounts, (output, "/logs")]:
        spec = f"type=bind,source={source.resolve()},target={target}"
        if target != "/logs":
            spec += ",readonly"
        args += ["--mount", spec]
    args += [image, *command]
    write(output / "invocation.json", {"argv": args, "network": "none", "agent_or_model_invoked": False})
    with (output / "stdout.txt").open("wb") as out, (output / "stderr.txt").open("wb") as err:
        result = subprocess.run(args, cwd=ROOT, stdout=out, stderr=err, timeout=180)
    if result.returncode not in allowed_codes:
        raise RuntimeError(f"Verifier execution error in {label}: exit {result.returncode}; inspect saved logs")
    return output, result.returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="sec-verifier-replay:20261103")
    args = parser.parse_args()
    independent = BASE / "independent_answers"
    recovered = ROOT / "diagnosis/recovered_output/answers.json"
    provenance = json.loads((recovered.with_name("provenance.json")).read_text())
    assert digest(recovered) == provenance["recovered_file_sha256"]
    official_test = ROOT / "evaluation/source/original_verifier/test_outputs.py"
    official_gt = ROOT / "verifier/expected_output.json"
    sources = json.loads((ROOT / "evaluation/source/SOURCES.json").read_text())
    for relative, path in [("verifier/test_outputs.py", official_test), ("verifier/expected_output.json", official_gt)]:
        original = next(r for r in sources["original_files"] if r["path"] == relative)
        assert git_blob(path) == original["git_blob"], "Original verifier/GT changed"
    before = {str(p.relative_to(ROOT)).replace("\\", "/"): digest(p) for p in [official_test, official_gt]}
    official = []
    for label, actual in [("historical", recovered), ("independent_original", independent / "original/answers.json")]:
        directory, code = run(args.image, "official_" + label,
            [(actual, "/root/answers.json"), (official_test, "/verifier/test_outputs.py"), (official_gt, "/verifier/expected_output.json")],
            ["python", "-m", "pytest", "--ctrf", "/logs/ctrf.json", "/verifier/test_outputs.py",
             "--tb=no", "-rN", "-q", "-p", "no:cacheprovider"], (0, 1))
        ctrf = json.loads((directory / "ctrf.json").read_text())
        result = {"case": label, "exit_code": code,
                  "summary": ctrf["results"]["summary"],
                  "tests": [{"name": r["name"], "status": r["status"]} for r in ctrf["results"]["tests"]]}
        assert result["summary"]["tests"] == 2
        if label == "independent_original":
            assert code == 0 and result["summary"]["passed"] == 2
        official.append(result)
        print(json.dumps({"official": label, "passed": result["summary"]["passed"], "failed": result["summary"]["failed"]}), flush=True)
    native = []
    for label, actual, reference in [("historical", recovered, official_gt),
            ("original", independent / "original/answers.json", official_gt),
            *[(g, independent / g / "answers.json", ROOT / f"evaluation/{g}/verifier/reference_answers.json")
              for g in ["group_01", "group_02", "group_03"]]]:
        directory, code = run(args.image, "accuracy_" + label,
            [(actual, "/root/answers.json"), (ROOT / "verifier", "/verifier"), (reference, "/reference.json")],
            ["python", "/verifier/native_grade.py", "--actual", "/root/answers.json", "--reference", "/reference.json", "--log-dir", "/logs"])
        report = json.loads((directory / "accuracy.json").read_text())
        result = {"case": label, "accuracy": report["accuracy"], "correct_items": report["correct_items"],
                  "expected_items": report["expected_items"], "strict_success": report["strict_success"],
                  "extra_error_items": report["extra_error_items"], "answers_sha256": digest(actual),
                  "reference_sha256": digest(reference), "report": str((directory / "accuracy.json").relative_to(ROOT)).replace("\\", "/")}
        if label != "historical":
            assert result["accuracy"] == 1 and result["strict_success"]
        native.append(result)
        print(json.dumps({k: result[k] for k in ["case", "accuracy", "correct_items", "expected_items"]}), flush=True)
    assert before == {p: digest(ROOT / p) for p in before}, "Verifier/GT altered during grading"
    historical = native[0]
    historical_detail = json.loads((ROOT / historical["report"]).read_text())
    question_results = {q: {"correct": sum(r["correct"] for r in historical_detail["item_feedback"] if r["item"].startswith(q)),
                            "items": sum(r["item"].startswith(q) for r in historical_detail["item_feedback"])}
                        for q in ["q1_answer", "q2_answer", "q3_answer", "q4_answer"]}
    image_id = subprocess.check_output(["docker", "image", "inspect", "--format", "{{.Id}}", args.image], cwd=ROOT).decode().strip()
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "kind": "verifier_only_replay",
              "image": args.image, "image_id": image_id, "grading_network": "none",
              "bootstrap_change": "Preinstall pinned pytest 8.4.1 and pytest-json-ctrf 0.3.5, bypassing failed online apt/curl/uv bootstrap; official test code and GT unchanged.",
              "official_verifier_and_gt_sha256": before, "official_core": official, "accuracy_verifier": native,
              "historical_question_results": question_results,
              "historical_original_verifier_healthy": False,
              "recovered_output_grade_verified": True,
              "effective_task_outcome": "PASS" if historical["strict_success"] else "FAIL",
              "reference_outputs_computed_independently_from_input": True,
              "all_reference_outputs_pass_current_verifier": all(r["strict_success"] for r in native[1:]),
              "reference_answer_items_passed": sum(r["correct_items"] for r in native[1:]),
              "historical_file_independently_archived": False,
              "recovered_output_provenance": "diagnosis/recovered_output/provenance.json",
              "new_model_calls": 0, "docker_grader_runs": 7, "new_agent_rollouts": 0,
              "full_original_task_environment_rebuilt": False}
    write(BASE / "SUMMARY.json", report)


if __name__ == "__main__":
    main()
