"""Score three frozen 20-receipt groups offline; never launch an agent."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "verifier"))
from score_accuracy import score, summarize

GROUPS = ("group_01", "group_02", "group_03")


def load_groups(root=ROOT):
    manifest = json.loads((Path(root) / "manifest.json").read_text(encoding="utf-8"))
    groups = manifest["groups"]
    if set(groups) != set(GROUPS):
        raise ValueError("Expected exactly the three frozen generalization groups")
    names = []
    source_ids = []
    for group in GROUPS:
        members = groups[group]
        if len(members) != 20:
            raise ValueError("Every frozen group must contain exactly 20 receipts")
        filenames = [row["filename"] for row in members]
        if filenames != sorted(filenames) or len(set(filenames)) != 20:
            raise ValueError("Frozen filenames must be sorted and unique")
        if any(not isinstance(name, str) or not name or Path(name).name != name
               or "/" in name or "\\" in name or name in (".", "..") for name in filenames):
            raise ValueError("Frozen filenames must be plain filenames")
        names.extend(filenames)
        source_ids.extend(row["source_id"] for row in members)
    if len(set(names)) != 60 or len(set(source_ids)) != 60:
        raise ValueError("The three groups must not repeat a filename or source receipt")
    return groups


def group_spec(members):
    return {"expected_receipts": 20, "filenames": [row["filename"] for row in members]}


def evaluate(predictions, root=ROOT):
    root = Path(root)
    groups = load_groups(root)
    reports, observations = {}, []
    for group in GROUPS:
        report = score(Path(predictions) / group / "stat_ocr.xlsx",
                       root / group / "stat_oracle.xlsx", group_spec(groups[group]))
        reports[group] = report
        observations.extend(dict(row, group=group) for row in report["field_feedback"])
    return {"schema_version": 1, "task": "jpg-ocr-stat-generalization",
            "groups": reports, "overall": summarize(observations),
            "missing_predictions_keep_fixed_denominator": True,
            "answer_values_exported": False, "model_calls": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", required=True, type=Path,
                        help="Root containing group_01/stat_ocr.xlsx through group_03/stat_ocr.xlsx")
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    result = evaluate(args.predictions)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(args.report), "overall": result["overall"], "model_calls": 0}))


if __name__ == "__main__":
    main()
