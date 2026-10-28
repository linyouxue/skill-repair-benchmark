"""Native verifier: per-item accuracy reward and separate strict task pass."""
import json
from pathlib import Path
import subprocess
import sys
import time
import os
import shutil

LOG = Path(os.environ.get("PFG_VERIFIER_LOG_DIR", "/logs/verifier"))


def run_logged(args, cwd, stem, timeout):
    with (LOG/f"{stem}.stdout").open("wb") as stdout, (LOG/f"{stem}.stderr").open("wb") as stderr:
        try:
            result = subprocess.run(args,cwd=cwd,stdout=stdout,stderr=stderr,timeout=timeout)
        except subprocess.TimeoutExpired:
            if stem == "flink":
                return False
            raise
    if result.returncode:
        text = (LOG/f"{stem}.stdout").read_text(errors="replace")+(LOG/f"{stem}.stderr").read_text(errors="replace")
        if stem == "maven" and ("COMPILATION ERROR" in text or "Compilation failure" in text):
            return False
        if stem == "flink":
            if any(marker in text for marker in ["clusterdata.query.LongestSessionPerJob",
                    "JobExecutionException", "Could not load the provided entrypoint class"]):
                return False
        # Preserve an undecided runtime/build failure for classification; no fake reward.
        raise RuntimeError(f"{stem} failed ({result.returncode}); inspect verifier logs before classifying")
    return True


def finish(report, tests, started):
    now = int(time.time()*1000)
    passed = sum(r["status"]=="passed" for r in tests)
    reward = float(report["score"])
    strict_success = bool(tests) and passed == len(tests)
    report.update({"task_passed":strict_success,"strict_success":strict_success,
                   "reward":reward,"data_version":"pilot-v2","scoring_version":"item-accuracy-v1"})
    ctrf = {"results":{"tool":{"name":"generalization-item-accuracy-v1"},
        "summary":{"tests":len(tests),"passed":passed,"failed":len(tests)-passed,
                   "pending":0,"skipped":0,"other":0,"start":started,"stop":now},"tests":tests}}
    (LOG/"accuracy.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    (LOG/"ctrf.json").write_text(json.dumps(ctrf,indent=2)+"\n",encoding="utf-8")
    (LOG/"reward.txt").write_text(str(reward),encoding="utf-8")


def main():
    started = int(time.time()*1000)
    began = time.monotonic()
    LOG.mkdir(parents=True,exist_ok=True)
    for stale in ["reward.txt","accuracy.json","ctrf.json","evaluation_error.json"]:
        (LOG / stale).unlink(missing_ok=True)
    task = sys.argv[1]
    if task == "pddl-airport-planning":
        from score_pddl import score
        base = Path("/app")
        report = score(base,base)
        tests = [{"name":item["id"],"status":"passed" if item["valid"] else "failed"}
                 for item in report["plans"]]
    else:
        from score_flink import score
        base = Path("/app/workspace")
        if not run_logged(["mvn","clean","package","-q"],base,"maven",480):
            finish({"failure_class":"candidate_compile_error","score":0.0,"accuracy":0.0,
                    "metric":"job_decision_accuracy","job_accuracy":0.0},
                   [{"name":"candidate_compilation","status":"failed"}],started)
            return
        actual = LOG / "actual-flink.txt"
        if actual.is_dir():
            if not actual.resolve().is_relative_to(LOG.resolve()):
                raise RuntimeError("Refusing to clear an output outside verifier logs")
            shutil.rmtree(actual)
        else:
            actual.unlink(missing_ok=True)
        # Original outer verifier deadline is 600s; leave 20s for reports.
        runtime_budget = min(300,max(1,int(580-(time.monotonic()-began))))
        if not run_logged(["/opt/flink/bin/flink","run","-t","local","-c","clusterdata.query.LongestSessionPerJob",
            str(base/"target/LongestSessionPerJob-jar-with-dependencies.jar"),"--task_input",
            str(base/"data/task_events/part-00001-of-00500.csv.gz"),"--job_input",
            str(base/"data/job_events/part-00001-of-00500.csv.gz"),"--output",str(actual)],base,"flink",runtime_budget):
            finish({"failure_class":"candidate_runtime_error_or_timeout","score":0.0,"accuracy":0.0,
                    "metric":"job_decision_accuracy","job_accuracy":0.0},
                   [{"name":"candidate_execution","status":"failed"}],started)
            return
        negatives_path = Path("/verifier/negative_ids.json")
        negatives = json.loads(negatives_path.read_text()) if negatives_path.exists() else {}
        report = score(actual,json.loads(Path("/verifier/expected.json").read_text()),negatives)
        tests = [{"name":"job:"+r["job_id"],"status":"passed" if r["correct"] else "failed"} for r in report["job_feedback"]]
        tests.extend({"name":"exclude:"+r["job_id"],"status":"passed" if r["correct"] else "failed"} for r in report["negative_feedback"])
        if report["delivery_issues"]:
            tests.append({"name":"delivery_contract","status":"failed"})
    finish(report,tests,started)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        LOG.mkdir(parents=True,exist_ok=True)
        (LOG/"evaluation_error.json").write_text(json.dumps({"type":type(exc).__name__,"message":str(exc)}),encoding="utf-8")
        raise
