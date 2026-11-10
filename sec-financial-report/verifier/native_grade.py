"""Native test-script entry point; standard library only, no network installation."""
import argparse
import json
from pathlib import Path
import time
from score_accuracy import load_reference, score


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actual", type=Path, default=Path("/root/answers.json"))
    parser.add_argument("--reference", type=Path, default=Path(__file__).with_name("expected_output.json"))
    parser.add_argument("--log-dir", type=Path, default=Path("/logs/verifier"))
    args = parser.parse_args()
    args.log_dir.mkdir(parents=True, exist_ok=True)
    for name in ["reward.txt", "accuracy.json", "ctrf.json", "evaluation_error.json"]:
        (args.log_dir / name).unlink(missing_ok=True)
    started = int(time.time() * 1000)
    try:
        report = score(args.actual, load_reference(args.reference))
        tests = [{"name": f"{r['case_id']}:{r['item']}", "status": "passed" if r["correct"] else "failed"}
                 for r in report["item_feedback"]]
        tests.extend({"name": f"extra_output:{i+1}", "status": "failed"} for i in range(report["extra_error_items"]))
        passed = report["correct_items"]
        ctrf = {"results": {"tool": {"name": "sec-seven-question-v2"},
                "summary": {"tests": len(tests), "passed": passed, "failed": len(tests) - passed,
                            "pending": 0, "skipped": 0, "other": 0,
                            "start": started, "stop": int(time.time() * 1000)}, "tests": tests}}
        for name, data in [("accuracy.json", report), ("ctrf.json", ctrf)]:
            (args.log_dir / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (args.log_dir / "reward.txt").write_text(str(report["reward"]) + "\n", encoding="utf-8")
    except Exception as exc:
        (args.log_dir / "evaluation_error.json").write_text(json.dumps({"type": type(exc).__name__, "message": str(exc)}), encoding="utf-8")
        raise


if __name__ == "__main__":
    main()
