"""Build the actual original and exported task environments, then grade independent fixtures. No model."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "validation/task_environments_single_case"
loader = importlib.util.spec_from_file_location("sec_export", ROOT / "evaluation/prepare_task.py")
exporter = importlib.util.module_from_spec(loader)
loader.loader.exec_module(exporter)
PROBE = """import importlib.metadata,json,pathlib,subprocess,sys
import pandas as pd
periods=sys.argv[1:3]
tables=['COVERPAGE','SUBMISSION','SUMMARYPAGE','INFOTABLE']
for period in periods:
    for table in tables:
        path=pathlib.Path('/root')/period/(table+'.tsv')
        frame=pd.read_csv(path,sep='\\t',dtype=str,nrows=1)
        assert len(frame)==1 and 'ACCESSION_NUMBER' in frame.columns
assert pd.__version__=='2.3.3'
assert importlib.metadata.version('rapidfuzz')=='3.14.3'
print(json.dumps({'periods':periods,'tables_read':8,'pandas':pd.__version__,'rapidfuzz':importlib.metadata.version('rapidfuzz')}),flush=True)
subprocess.run(['python3','/verifier/native_grade.py'],check=True)
"""


def command(args, directory, stem, timeout):
    with (directory / (stem + ".stdout.txt")).open("wb") as out, (directory / (stem + ".stderr.txt")).open("wb") as err:
        result = subprocess.run(args, cwd=ROOT, stdout=out, stderr=err, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"{stem} failed: {directory.name}, exit {result.returncode}; inspect saved logs")


def main():
    reports = []
    with tempfile.TemporaryDirectory(prefix="sec-env-") as temporary:
        for group in ["original", "group_01", "group_02", "group_03"]:
            directory = LOG / group
            directory.mkdir(parents=True, exist_ok=True)
            actual = ROOT / "validation/verifier_replay/independent_answers" / group / "answers.json"
            assert actual.is_file(), "Compute independent answers before environment checks"
            if group == "original":
                environment, verifier = ROOT / "environment", ROOT / "verifier"
                periods = ["2025-q2", "2025-q3"]
            else:
                task = exporter.prepare(group, Path(temporary) / group / "sec-financial-report")
                environment, verifier = task / "environment", task / "verifier"
                spec = json.loads((task / "EXPORT.json").read_text(encoding="utf-8"))
                periods = [spec["baseline_period"], spec["current_period"]]
                answer = json.loads(actual.read_text(encoding="utf-8"))[spec["case_id"]]
                actual = Path(temporary) / group / "answers.json"
                actual.write_text(json.dumps(answer), encoding="utf-8")
            tag = "sec-env-check-" + group.replace("_", "-") + ":" + uuid.uuid4().hex[:10]
            build = ["docker", "build", "--pull=false", "-t", tag, str(environment)]
            print(json.dumps({"building_environment": group}), flush=True)
            command(build, directory, "build", 600)
            image_id = subprocess.check_output(["docker", "image", "inspect", "--format", "{{.Id}}", tag], cwd=ROOT).decode().strip()
            try:
                run = ["docker", "run", "--rm", "--network", "none", "--env", "PYTHONDONTWRITEBYTECODE=1"]
                for source, target, readonly in [(verifier, "/verifier", True), (actual, "/root/answers.json", True), (directory, "/logs/verifier", False)]:
                    run += ["--mount", f"type=bind,source={source.resolve()},target={target}" + (",readonly" if readonly else "")]
                run += [tag, "python3", "-c", PROBE, *periods]
                (directory / "invocation.json").write_text(json.dumps({"build": build, "run": run, "image_id": image_id,
                    "actual_is_independent_calculation_not_model_output": True}, indent=2) + "\n", encoding="utf-8")
                command(run, directory, "probe_and_grade", 180)
                accuracy = json.loads((directory / "accuracy.json").read_text(encoding="utf-8"))
                assert accuracy["accuracy"] == 1 and accuracy["strict_success"]
                report = {"group": group, "image_id": image_id, "periods": periods,
                          "table_files_read": 8, "accuracy": accuracy["accuracy"],
                          "answer_items": accuracy["expected_items"], "network_during_grading": "none",
                          "probe_and_grade_exit_code": 0}
                reports.append(report)
                print(json.dumps(report), flush=True)
            finally:
                # Only remove the uniquely named image built by this check, without force.
                command(["docker", "image", "rm", tag], directory, "cleanup_image", 60)
    result = {"checked_at": datetime.now(timezone.utc).isoformat(), "kind": "task_environment_and_verifier_check",
              "environments": reports, "environment_builds": 4, "docker_probe_and_grade_runs": 4,
              "independent_answer_items_accepted": sum(r["answer_items"] for r in reports),
              "new_model_calls": 0, "new_agent_rollouts": 0, "temporary_task_exports_removed": True,
              "temporary_images_removed": True, "original_task_and_skill_and_gt_unchanged": True}
    (LOG / "SUMMARY.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
