"""Score actual Flink tuple output; never print reference tuple values."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

TUPLE = re.compile(r"\(\s*(\d+)\s*,\s*(\d+)\s*\)")


def score(actual, expected, negative_ids=None):
    negative_ids = negative_ids or {}
    rows = []
    issues = []
    invalid_records = 0
    readable_output = True
    if actual.is_dir():
        files = sorted(p for p in actual.rglob("*") if p.is_file() and not p.name.startswith((".", "_")))
    else:
        files = [actual] if actual.is_file() else []
    if not files:
        issues.append("missing_output")
        readable_output = False
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (UnicodeError, OSError):
            issues.append(f"unreadable_output:{path.name}")
            readable_output = False
            continue
        for line_no, line in enumerate(lines, 1):
            if not line.strip():
                continue
            match = TUPLE.fullmatch(line.strip())
            if not match:
                issues.append(f"invalid_tuple:{path.name}:{line_no}")
                invalid_records += 1
            else:
                rows.append((match[1], int(match[2])))
    counts = Counter(job for job, _ in rows)
    predictions = dict(rows)
    duplicates = sorted(job for job,n in counts.items() if n > 1)
    extras = sorted(set(predictions) - set(expected))
    if duplicates:
        issues.append(f"duplicate_jobs:{len(duplicates)}")
    if extras:
        issues.append(f"unexpected_jobs:{len(extras)}")
    feedback = [{"job_id": job, "correct": readable_output and counts[job] == 1 and predictions.get(job) == value}
                for job,value in expected.items()]
    correct = sum(item["correct"] for item in feedback)
    negative_feedback = [{"job_id":job,"stratum":kind,"correct":readable_output and counts[job] == 0}
                         for kind,ids in negative_ids.items() for job in ids]
    negative_correct = sum(item["correct"] for item in negative_feedback)
    known_ids = set(expected) | {item["job_id"] for item in negative_feedback}
    unknown_ids = sorted(set(predictions) - known_ids)
    # Each supplied job is one decision: exact tuple, or required exclusion.
    # Unknown output jobs and malformed records are additional wrong items;
    # known negative jobs are already counted and must not be penalized twice.
    correct_items = correct + negative_correct
    extra_error_items = len(unknown_ids) + invalid_records
    total_items = len(expected) + len(negative_feedback) + extra_error_items
    accuracy = correct_items / total_items if total_items else 0.0
    strict_success = bool(expected) and correct == len(expected) and negative_correct == len(negative_feedback) and not issues
    key_precision = len(set(predictions) & set(expected))/len(predictions) if predictions else 0.0
    return {"score":accuracy,"accuracy":accuracy,"metric":"job_decision_accuracy",
            "scoring_version":"item-accuracy-v1","correct_items":correct_items,"total_items":total_items,
            "extra_error_items":extra_error_items,"unknown_output_jobs":unknown_ids,
            "strict_success":strict_success,
            "job_accuracy":accuracy,
            "positive_job_accuracy":correct / len(expected) if expected else 0.0,
            "correct_jobs": correct, "total_jobs": len(expected), "delivery_issues": issues,
            "task_passed":strict_success,
            "output_key_precision":key_precision,
            "output_key_recall":len(set(predictions) & set(expected))/len(expected) if expected else 0.0,
            "negative_jobs":len(negative_feedback),"correct_negative_jobs":negative_correct,
            "negative_feedback":negative_feedback,"job_feedback": feedback}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--actual", required=True, type=Path)
    parser.add_argument("--expected", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--negative-ids", type=Path)
    args = parser.parse_args()
    expected = json.loads(args.expected.read_text(encoding="utf-8"))
    negative_path = args.negative_ids or args.expected.with_name("negative_ids.json")
    negatives = json.loads(negative_path.read_text()) if negative_path.exists() else {}
    result = score(args.actual, expected, negatives)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k not in {"job_feedback","negative_feedback"}}))


if __name__ == "__main__":
    main()
