"""Score the 100 answer positions in an SEC v2 answers.json."""

import argparse
import json
import math
from pathlib import Path

VERSION = "sec-seven-question-v2"
CASE_IDS = tuple(f"case_{i:03d}" for i in range(1, 11))
KEYS = tuple(f"q{i}_answer" for i in range(1, 8))


def load_reference(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if set(data) != set(CASE_IDS):
        raise ValueError("Reference must have exactly the ten case IDs")
    for row in data.values():
        if set(row) != set(KEYS) or any(type(row[k]) is not int or row[k] <= 0 for k in KEYS[:4]):
            raise ValueError("Invalid numeric reference")
        if any(not isinstance(row[k], list) or len(row[k]) != 2
               or any(not isinstance(v, str) or not v for v in row[k]) or len(set(row[k])) != 2
               for k in KEYS[4:]):
            raise ValueError("Invalid ranked reference")
    return data


def number(value):
    return type(value) is int or (type(value) is float and math.isfinite(value))


def value_correct(value, expected):
    if not number(value):
        return False
    try:
        return abs(value / expected - 1) < 0.001
    except ArithmeticError:
        return False


def score(actual_path, reference):
    issues = []
    try:
        actual = json.loads(Path(actual_path).read_text(encoding="utf-8"))
        if not isinstance(actual, dict):
            raise ValueError("Expected a JSON object")
    except (OSError, UnicodeError, ValueError):
        actual = {}
        issues.append("answers_missing_unreadable_or_invalid")
    feedback = []
    extra = len(set(actual) - set(reference))
    for case_id, expected in reference.items():
        answer = actual.get(case_id, {})
        if not isinstance(answer, dict):
            answer = {}
        checks = []
        for i, key in enumerate(KEYS[:4]):
            value = answer.get(key)
            correct = (value_correct(value, expected[key]) if i < 2
                       else number(value) and value == expected[key])
            checks.append((key, correct))
        for key in KEYS[4:]:
            values = answer.get(key)
            if not isinstance(values, list):
                values = []
            extra += max(0, len(values) - 2)
            for pos, target in enumerate(expected[key]):
                value = values[pos] if pos < len(values) else None
                correct = isinstance(value, str) and (
                    value.lower() == target.lower() if key == KEYS[-1] else value == target
                )
                checks.append((f"{key}[{pos + 1}]", correct))
        feedback.extend({"case_id": case_id, "item": item, "correct": bool(correct)} for item, correct in checks)
    correct = sum(row["correct"] for row in feedback)
    expected = len(feedback)
    accuracy = correct / (expected + extra)
    return {"dataset_version": VERSION, "accuracy": accuracy, "reward": accuracy,
            "correct_items": correct, "expected_items": expected, "denominator": expected + extra,
            "extra_error_items": extra, "strict_success": correct == expected and not extra and not issues,
            "delivery_issues": issues, "item_feedback": feedback}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actual", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = score(args.actual, load_reference(args.reference))
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("accuracy", "correct_items", "denominator")}))
