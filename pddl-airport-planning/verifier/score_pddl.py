"""Validate plans by execution semantics, accepting only explicit VALID status."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCAL_RUNTIME = ROOT / ".runtime/site-packages"
if LOCAL_RUNTIME.exists():
    sys.path.insert(0, str(LOCAL_RUNTIME))


def validate(domain, problem_path, plan):
    from unified_planning.io import PDDLReader
    if not plan.is_file():
        return {"status": "missing_plan", "valid": False}
    problem = PDDLReader().parse_problem(str(domain), str(problem_path))
    return validate_loaded(problem, plan)


def validate_loaded(problem, plan):
    from unified_planning.engines import ValidationResultStatus
    from unified_planning.io import PDDLReader
    from unified_planning.shortcuts import PlanValidator
    if not plan.is_file():
        return {"status": "missing_plan", "valid": False}
    reader = PDDLReader()
    try:
        candidate = reader.parse_plan(problem, str(plan))
    except Exception as exc:
        return {"status": "invalid_plan_syntax", "valid": False, "error_type": type(exc).__name__}
    with PlanValidator(problem_kind=problem.kind, plan_kind=candidate.kind) as validator:
        result = validator.validate(problem, candidate)
    if result.status not in {ValidationResultStatus.VALID, ValidationResultStatus.INVALID}:
        raise RuntimeError(f"Validator did not decide plan validity: {result.status.name}")
    return {"status": result.status.name, "valid": result.status == ValidationResultStatus.VALID,
            "action_count": len(candidate.actions)}


def score(inputs, plans):
    entries = json.loads((inputs / "problem.json").read_text(encoding="utf-8"))
    outcomes = [{"id": item["id"], **validate(inputs / item["domain"], inputs / item["problem"],
                                            plans / item["plan_output"])} for item in entries]
    correct = sum(item["valid"] for item in outcomes)
    accuracy = correct / len(entries) if entries else 0.0
    strict_success = bool(entries) and correct == len(entries)
    return {"score":accuracy,"accuracy":accuracy,"metric":"plan_validity_rate",
            "scoring_version":"item-accuracy-v1","plan_validity_rate":accuracy,
            "valid_plans":correct,"total_plans":len(entries),
            "correct_items":correct,"total_items":len(entries),
            "strict_success":strict_success,"task_passed":strict_success,"plans":outcomes}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--plans", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    result = score(args.inputs, args.plans)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
