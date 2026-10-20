"""Validate completed CTRF evidence before publishing a fractional native reward."""

import argparse
import json
from pathlib import Path


def validated_reward(ctrf, accuracy):
    summary = ctrf["results"]["summary"]
    tests = ctrf["results"]["tests"]
    if len(tests) != 44 or summary.get("tests") != 44:
        raise ValueError("Expected exactly 44 completed field checks")
    if any(test.get("status") not in ("passed", "failed") for test in tests):
        raise ValueError("Incomplete or erroneous field checks")
    passed = sum(test["status"] == "passed" for test in tests)
    failed = 44 - passed
    if summary.get("passed") != passed or summary.get("failed") != failed:
        raise ValueError("CTRF totals disagree with individual checks")
    if any(summary.get(key, 0) != 0 for key in ("skipped", "pending", "other", "errors")):
        raise ValueError("CTRF contains incomplete checks or infrastructure errors")
    scores = accuracy["all_receipts"]
    rows = accuracy["field_feedback"]
    if scores["receipts"] != 22 or scores["fields"] != 44 or len(rows) != 22:
        raise ValueError("Accuracy report has the wrong fixed denominator")
    if len({row["filename"] for row in rows}) != 22:
        raise ValueError("Accuracy report has duplicate receipt identifiers")
    flags = [row[f"{field}_correct"] for row in rows for field in ("date", "amount")]
    if any(type(flag) is not bool for flag in flags) or sum(flags) != passed:
        raise ValueError("Accuracy flags disagree with completed CTRF checks")
    reward = passed / 44
    if scores["field_correct"] != passed or scores["field_accuracy"] != reward or accuracy["reward"] != reward:
        raise ValueError("Accuracy summary disagrees with completed CTRF checks")
    return reward


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ctrf", type=Path, default=Path("/logs/verifier/ctrf.json"))
    parser.add_argument("--accuracy", type=Path, default=Path("/logs/verifier/accuracy.json"))
    parser.add_argument("--reward", type=Path, default=Path("/logs/verifier/reward.txt"))
    args = parser.parse_args()
    args.reward.unlink(missing_ok=True)
    reward = validated_reward(
        json.loads(args.ctrf.read_text(encoding="utf-8")),
        json.loads(args.accuracy.read_text(encoding="utf-8")),
    )
    args.reward.write_text(f"{reward:.17g}\n", encoding="utf-8")
    print(json.dumps({"reward": reward, "field_correct": round(reward * 44), "fields": 44}))


if __name__ == "__main__":
    main()
