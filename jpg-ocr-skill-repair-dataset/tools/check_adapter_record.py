"""Offline structural check only; never sends a model request."""
import argparse
import json
from pathlib import Path


def check(record, package):
    if record.get("record_kind") == "template_not_execution_evidence":
        raise ValueError("An empty template is not actual execution evidence")
    if record.get("test_material_used_for_repair") is not False:
        raise ValueError("Test material must be excluded from repair")
    if record.get("correct_answer_values_provided_to_diagnoser") is not False:
        raise ValueError("Correct answer values are not allowed in diagnosis input")
    stage = record.get("stage")
    if type(stage) is not int or stage not in range(1, 7):
        raise ValueError("stage must be 1..6")
    manifest_path = Path(record["batch_manifest"])
    if manifest_path.is_absolute() or ".." in manifest_path.parts or manifest_path.parts[0] != "train":
        raise ValueError("Only a package train manifest may be used")
    manifest = json.loads((package / manifest_path).read_text(encoding="utf-8"))
    if manifest["batch_id"] != f"batch_{stage:02d}" or record["batch_id"] != manifest["batch_id"]:
        raise ValueError("Fixed batch order differs")
    expected_images = set(manifest["image_ids"])
    expected_runs = {row["run_id"] for row in manifest["source_runs"]}
    if set(record.get("available_image_ids", [])) != expected_images:
        raise ValueError("All 20 source images must be available")
    if set(record.get("delivered_image_ids", [])) != expected_images:
        raise ValueError("All images need actual delivery records across native phases")
    if set(record.get("source_run_ids", [])) != expected_runs:
        raise ValueError("Use all three fixed source repeats")
    if not record.get("native_phases") or not record.get("actual_request_records") or not record.get("actual_delivery_receipts"):
        raise ValueError("Actual native phases, requests and delivery receipts are required")
    if not record.get("trajectory_ranges"):
        raise ValueError("Record the trajectory ranges actually consumed")
    return {"structural_check_passed": True, "checked_images": 20, "checked_source_runs": 3,
            "model_calls_by_checker": 0,
            "receipt_authenticity_and_model_understanding_not_proven_by_this_check": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path)
    args = parser.parse_args()
    try:
        result = check(json.loads(args.record.read_text(encoding="utf-8")), Path(__file__).resolve().parents[1])
    except (KeyError, ValueError, OSError) as error:
        print(json.dumps({"structural_check_passed": False, "error": str(error)}))
        raise SystemExit(2)
    print(json.dumps(result))
