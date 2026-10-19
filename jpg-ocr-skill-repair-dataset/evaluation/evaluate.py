"""Score submitted Excel files offline, with separate fixed-denominator split reports."""

import argparse
import csv
import importlib.util
import json
import statistics
import sys
from pathlib import Path


ALIASES = {"train": "train", "test1": "test", "test2": "validation"}
STRATA = ("no_hint_conflict_detected", "hint_conflict_unique_payment", "literal_rule_ambiguous")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_helpers(package):
    # Reuse the exact existing cell reading/format checks and field aggregation.
    # Do NOT call score(), load_checker(), test_outputs(), pytest or a native verifier.
    runtime = package / "evaluation_only/runtime"
    sys.path.insert(0, str(runtime))
    try:
        spec = importlib.util.spec_from_file_location("jpg_existing_score_helpers", runtime / "score_extended.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.read_predictions, module.summarize
    finally:
        sys.path.pop(0)


def split_data(package, split):
    legacy = ALIASES[split]
    manifest = read(package / "evaluation_only/runtime/curator/frozen_manifest.json")
    rows = [row for row in manifest if row["split"] == legacy]
    expected = 120 if split == "train" else 40
    if len(rows) != expected:
        raise ValueError("Frozen split size differs")
    prefix = "train" if split == "train" else "evaluation_only/" + split
    groups = [read(p) for p in sorted((package / prefix / "batches").glob("batch_*/manifest.json"))]
    if len(groups) != expected // 20:
        raise ValueError("Frozen batch count differs")
    names = [name for group in groups for name in group["image_ids"]]
    if len(names) != len(set(names)) or set(names) != {r["filename"] for r in rows}:
        raise ValueError("Frozen batch membership differs")
    return {row["filename"]: row for row in rows}, groups


def resolve_inputs(split, groups, inputs=None, predictions_dir=None, layout="batches"):
    if inputs:
        inputs = Path(inputs).resolve()
        data = read(inputs)
        if data.get("split") != split or data.get("layout", "batches") != layout:
            raise ValueError("Submission split/layout differs from CLI")
        if {r["repeat"] for r in data["rounds"]} != {1, 2, 3} or len(data["rounds"]) != 3:
            raise ValueError("Submission must describe repeats 1, 2 and 3 exactly once")
        result = {}
        for row in data["rounds"]:
            expected_keys = {g["batch_id"] for g in groups} if layout == "batches" else {"merged"}
            files = row["files"]
            if set(files) != expected_keys:
                raise ValueError("Submission file keys differ from frozen batch plan")
            for key, value in files.items():
                # Explicit null represents a known missing delivery, not an omitted sample.
                result[(row["repeat"], key)] = None if value is None else (inputs.parent / value).resolve()
        return result
    root = Path(predictions_dir).resolve()
    return {(repeat, group["batch_id"] if layout == "batches" else "merged"):
            root / f"round_{repeat:02d}" / group["batch_id"] / "stat_ocr.xlsx"
            if layout == "batches" else root / f"round_{repeat:02d}/stat_ocr.xlsx"
            for repeat in (1, 2, 3) for group in groups}


def evaluate(package, split, sources, layout="batches", method="unspecified"):
    read_predictions, summarize = load_helpers(package)
    labels, groups = split_data(package, split)
    per_batch, observations, delivery = [], [], []
    for repeat in (1, 2, 3):
        cache = {}
        for group in groups:
            key = group["batch_id"] if layout == "batches" else "merged"
            actual = sources[(repeat, key)]
            expected_names = group["image_ids"] if layout == "batches" else sorted(labels)
            if key not in cache:
                if actual is None:
                    cache[key] = ({}, ["output_missing"], [])
                else:
                    cache[key] = read_predictions(actual, expected_names)
                delivery.append({"repeat": repeat, "input_id": key,
                                 "excel_provided": actual is not None and actual.is_file(),
                                 "delivery_issues": cache[key][1]})
            predictions, issues, _ = cache[key]
            batch_rows = []
            for filename in group["image_ids"]:
                label = labels[filename]
                predicted = predictions.get(filename, ["", ""])
                row = {"repeat": repeat, "batch_id": group["batch_id"], "filename": filename,
                       "date_correct": predicted[0] == label["ground_truth"]["date"],
                       "amount_correct": predicted[1] == label["ground_truth"]["total_amount"],
                       "stratum": label["evaluation_stratum"],
                       "prediction_present": filename in predictions}
                observations.append(row)
                batch_rows.append(row)
            per_batch.append({"repeat": repeat, "batch_id": group["batch_id"],
                              "delivery_issues": issues, "contract_valid": not issues,
                              "all_receipts": summarize(batch_rows)})
    per_repeat = [{"repeat": repeat, **summarize([r for r in observations if r["repeat"] == repeat]),
                   "batches_with_valid_delivery": sum(b["contract_valid"] for b in per_batch if b["repeat"] == repeat)}
                  for repeat in (1, 2, 3)]
    overall = summarize(observations)
    means = [r["field_accuracy"] for r in per_repeat]
    summary = {"schema_version": 1, "method": method, "split": split, "legacy_split": ALIASES[split],
               "layout": layout, "unique_receipts": len(labels), "repeats": 3,
               "per_batch": per_batch, "per_repeat": per_repeat, "all_repeated_observations": overall,
               "field_accuracy_mean": statistics.mean(means),
               "field_accuracy_population_stddev": statistics.pstdev(means),
               "strata": {name: summarize([r for r in observations if r["stratum"] == name]) for name in STRATA},
               "input_files": delivery, "all_planned_excels_provided": all(d["excel_provided"] for d in delivery),
               "all_deliveries_contract_valid": all(not d["delivery_issues"] for d in delivery),
               "missing_predictions_keep_fixed_denominator": True,
               "field_scoring": "existing_cell_string_and_exact_date_amount_equality_no_new_normalization",
               "format_issues_reported_separately": True,
               "original_official_batch_reward": "not_executed_by_this_script",
               "model_calls": 0, "native_verifier_replays": 0, "answer_values_exported": False,
               "costs": "not_inferred_from_excel_report_method_costs_separately"}
    assert overall["fields"] == len(labels) * 3 * 2
    return summary, observations


def write_reports(output, summary, observations):
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Report directory is not empty; refusing to overwrite results")
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (output / "field_feedback.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(observations[0]))
        writer.writeheader()
        writer.writerows(observations)
    with (output / "batch_metrics.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["repeat", "batch_id", "field_correct", "fields", "field_accuracy", "date_accuracy", "amount_accuracy", "receipt_joint_accuracy", "contract_valid", "delivery_issues"])
        for row in summary["per_batch"]:
            m = row["all_receipts"]
            writer.writerow([row["repeat"], row["batch_id"], *[m[k] for k in ("field_correct", "fields", "field_accuracy", "date_accuracy", "amount_accuracy", "receipt_joint_accuracy")], row["contract_valid"], ";".join(row["delivery_issues"])])
    lines = [f"# {summary['split']}：{summary['method']} 的Excel离线评测", "",
             "| 遍次 | 字段正确率 | 日期正确率 | 金额正确率 | 整票正确率 |", "|---|---:|---:|---:|---:|"]
    for row in summary["per_repeat"]:
        lines.append(f"| {row['repeat']} | {row['field_accuracy']:.2%}（{row['field_correct']}/{row['fields']}） | {row['date_accuracy']:.2%} | {row['amount_accuracy']:.2%} | {row['receipt_joint_accuracy']:.2%} |")
    overall = summary["all_repeated_observations"]
    lines += ["", f"三遍字段均值：{summary['field_accuracy_mean']:.2%}；总体标准差：{summary['field_accuracy_population_stddev'] * 100:.2f}个百分点。",
              f"合计：{overall['field_correct']}/{overall['fields']}，字段正确率{overall['field_accuracy']:.2%}。", "",
              f"全部计划Excel已提供：{summary['all_planned_excels_provided']}；全部交付格式合格：{summary['all_deliveries_contract_valid']}。",
              "缺文件、缺行和未提取字段保留固定分母；格式问题另见batch_metrics.csv。该脚本未执行原官方整批verifier，不能将字段指标冒充官方reward。",
              "分集合独立报告，不混入其他划分、费用或baseline成绩。未调用模型，不导出正确答案值。", "",
              "| 分层 | 字段正确数/分母 | 字段正确率 |", "|---|---:|---:|"]
    for name, row in summary["strata"].items():
        percent = f"{row['field_accuracy']:.2%}" if row["fields"] else "无样本"
        lines.append(f"| {name} | {row['field_correct']}/{row['fields']} | {percent} |")
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--split", choices=ALIASES, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--predictions-dir", type=Path)
    source.add_argument("--inputs", type=Path, help="JSON explicitly mapping all repeats and inputs")
    parser.add_argument("--layout", choices=("batches", "merged"), default="batches")
    parser.add_argument("--method", default="unspecified")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    package = args.package.resolve()
    if args.out.resolve().is_relative_to(package):
        raise ValueError("Keep participant reports outside the frozen published dataset")
    _, groups = split_data(package, args.split)
    sources = resolve_inputs(args.split, groups, args.inputs, args.predictions_dir, args.layout)
    summary, observations = evaluate(package, args.split, sources, args.layout, args.method)
    write_reports(args.out, summary, observations)
    print(json.dumps({"split": args.split, "field_accuracy_mean": summary["field_accuracy_mean"],
                      "per_repeat_correct_fields": [r["field_correct"] for r in summary["per_repeat"]],
                      "fixed_total_fields": summary["all_repeated_observations"]["fields"],
                      "all_planned_excels_provided": summary["all_planned_excels_provided"],
                      "model_calls": 0, "native_verifier_replays": 0}))


if __name__ == "__main__":
    main()
