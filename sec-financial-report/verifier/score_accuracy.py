"""Score SEC answers under the original predicates, at answer-slot granularity."""
import argparse
import json
import math
from pathlib import Path


def load_reference(path):
    reference = json.loads(Path(path).read_text(encoding="utf-8"))
    if "q1_answer" in reference:
        # Directly reuse the untouched official training GT; no second training GT file.
        reference = {"dataset_version": "sec-original-accuracy-v1", "scoring_version": "sec-answer-accuracy-v1",
                     "layout": "single", "cases": {"original": reference}, "expected_answer_items": 10}
    if reference["layout"] not in {"single", "cases"} or not reference["cases"]:
        raise ValueError("Invalid reference layout")
    if reference["layout"] == "single" and len(reference["cases"]) != 1:
        raise ValueError("Single layout needs one reference case")
    for answer in reference["cases"].values():
        if not (number(answer["q1_answer"]) and answer["q1_answer"] > 0
                and number(answer["q2_answer"])
                and len(answer["q3_answer"]) == 5 and len(answer["q4_answer"]) == 3):
            raise ValueError("Invalid reference answer")
    if reference["expected_answer_items"] != 10 * len(reference["cases"]):
        raise ValueError("Invalid reference item count")
    return reference


def number(value):
    return type(value) in (int, float) and (type(value) is int or math.isfinite(value))


def q1_correct(actual, expected):
    if not number(actual):
        return False
    try:
        # This is the original test's strict 0.1% predicate, including its float arithmetic.
        return abs(actual / expected - 1) < 0.001
    except (ArithmeticError, ValueError):
        return False


def score(actual_path, reference):
    issues = []
    try:
        actual = json.loads(Path(actual_path).read_text(encoding="utf-8"))
        if not isinstance(actual, dict):
            raise ValueError("Top-level JSON must be an object")
    except (OSError, UnicodeError, ValueError):
        actual = {}
        issues.append("answers_missing_unreadable_or_invalid")
    expected_cases = reference["cases"]
    predicted_cases = ({next(iter(expected_cases)): actual}
                       if reference["layout"] == "single" else actual)
    feedback, extra = [], 0
    if reference["layout"] == "cases":
        extra = len(set(predicted_cases) - set(expected_cases))
    for case_id, expected in expected_cases.items():
        answer = predicted_cases.get(case_id, {})
        if not isinstance(answer, dict):
            answer = {}
        checks = [("q1_answer", q1_correct(answer.get("q1_answer"), expected["q1_answer"])),
                  ("q2_answer", number(answer.get("q2_answer")) and answer["q2_answer"] == expected["q2_answer"])]
        for key, length in [("q3_answer", 5), ("q4_answer", 3)]:
            ranked = answer.get(key, [])
            if not isinstance(ranked, list):
                ranked = []
            extra += max(0, len(ranked) - length)
            for rank in range(length):
                value = ranked[rank] if rank < len(ranked) else None
                target = expected[key][rank]
                correct = isinstance(value, str) and (value == target if key == "q3_answer" else value.lower() == target.lower())
                checks.append((f"{key}[{rank + 1}]", correct))
        feedback.extend({"case_id": case_id, "item": item, "correct": bool(correct)} for item, correct in checks)
    correct = sum(item["correct"] for item in feedback)
    denominator = reference["expected_answer_items"] + extra
    accuracy = correct / denominator
    strict = correct == reference["expected_answer_items"] and extra == 0 and not issues
    return {"metric": "answer_item_accuracy", "scoring_version": reference["scoring_version"],
            "dataset_version": reference["dataset_version"], "score": accuracy, "accuracy": accuracy,
            "reward": accuracy, "correct_items": correct, "expected_items": reference["expected_answer_items"],
            "extra_error_items": extra, "denominator": denominator,
            "strict_success": strict, "task_passed": strict, "delivery_issues": issues,
            "item_feedback": feedback, "runtime_weighted": False,
            "reference_values_in_feedback": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actual", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = score(args.actual, load_reference(args.reference))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ["accuracy", "correct_items", "denominator", "strict_success"]}))
