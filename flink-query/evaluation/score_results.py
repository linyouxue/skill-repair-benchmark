"""Score actual held-out output offline without calling a model or rerunning it."""
import argparse
import json
from pathlib import Path
import sys

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "verifier"))


def score_actual(group, actual):
    selected = PACKAGE / "evaluation" / group
    if group not in {"group_01", "group_02", "group_03"}:
        raise ValueError("Unknown frozen group")
    if PACKAGE.name == "pddl-airport-planning":
        from score_pddl import score
        result = score(selected / "inputs", Path(actual))
    else:
        from score_flink import score
        expected = json.loads((selected / "verifier/expected.json").read_text())
        negatives = json.loads((selected / "verifier/negative_ids.json").read_text())
        result = score(Path(actual), expected, negatives)
    result.update({"group": group, "data_version": "pilot-v2", "model_calls": 0,
                   "score_origin": "offline_actual_output_not_agent_rerun"})
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", required=True, choices=["group_01", "group_02", "group_03"])
    parser.add_argument("--actual", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    result = score_actual(args.group, args.actual)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"group": args.group, "score": result["score"], "strict_success": result["strict_success"], "model_calls": 0}))
