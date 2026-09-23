"""Expand the offline comparison to every evaluator summary metric."""
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent
def read(p):
    return json.loads(p.read_text(encoding="utf-8-sig"))
def pct(v):
    return str((Decimal(str(v)) * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) + "%"

scores = read(OUT / "scores.json")
summary = read(ROOT / "gold-evaluation/summary.json")
details = read(ROOT / "gold-evaluation/details.json")
passed = {r["task_id"] for r in scores["tasks"] if r["outcome"] == "PASS"}
by_id = {r["task_id"]: r for r in details["tasks"]}
versions = {}
for version, pr in scores["metrics"].items():
    m = {**summary["metrics"], **pr}
    if version != "original":
        m["failed_gold_repair_count"] = sum(t["metrics"]["failed_gold_repair_count"] for t in details["tasks"] if t["task_id"] not in passed)
        if version == "pass_task_full_credit":
            m["harmful_extra_repair_count"] = sum(t["metrics"]["harmful_extra_repair_count"] for t in details["tasks"] if t["task_id"] not in passed)
        m["location_accuracy"] = m["location_correct_count"] / m["diagnosis"]["tp"]
    assert m["repair"]["fp"] == m["failed_gold_repair_count"] + m["harmful_extra_repair_count"]
    versions[version] = {**summary, "metrics": m}

table = []
def row(label, vals, note=""):
    table.append([label, *[str(v) for v in vals], note])
for kind, label in (("diagnosis", "诊断"), ("repair", "修复")):
    for key in ("tp", "fp", "fn", "precision", "recall", "f1"):
        vals = [v["metrics"][kind][key] for v in versions.values()]
        row(label + " " + key.upper(), [pct(v) for v in vals] if key in ("precision", "recall", "f1") else vals)
notes = {
    "diagnosis_task_count": "参与诊断汇总的任务数",
    "location_correct_count": "保留原Gold定位命中，不因通过而增加",
    "location_accuracy": "定位正确数/诊断TP；新版6/17，原版6/8",
    "failed_gold_repair_count": "尝试修复但未正确完成的Gold缺陷；新版移除通过任务的8项",
    "harmful_extra_repair_count": "有害或无依据的额外改动；整体覆盖口径移除通过任务的1项",
    "substantively_modified_bundles": "存在实质修改的bundle数，沿用内容判定",
    "regressed_bundles": "内容裁判判为引入新缺陷的bundle数，沿用原判",
    "regression_rate": "发生回归的bundle/实质修改bundle=5/15；不是执行P→F率",
    "regression_count": "回归新缺陷数量，沿用原判",
    "possible_new_defect_count": "额外改动中的疑似新缺陷数；与回归计数不直接相加",
}
for key, note in notes.items():
    vals = [v["metrics"][key] for v in versions.values()]
    row(key, [pct(v) for v in vals] if key in ("location_accuracy", "regression_rate") else vals, note)
for key in ("task_count", "total_gold_defect_count", "evaluated_task_count", "evaluated_gold_defect_count", "scored_task_count", "skipped_original_pass_task_count", "skipped_gold_defect_count", "skipped_original_pass_rate", "confidence_task_count", "total_judgment_count", "low_confidence_count", "low_confidence_rate", "review_item_count", "blocking_review_count"):
    value = pct(summary[key]) if key.endswith("rate") else summary[key]
    row(key, [value] * 3, "原评测记录；未重新调用裁判")

lines = ["# 完整指标对照", "", "三列依次为原Gold评分、F→P任务TP覆盖且FP/FN清零、F→P的Gold缺陷全部计TP但保留额外FP。后两者均为离线替代统计，不是新的Gold裁判结果。", "",
         "定位保留原location_correct判定，并按脚本公式使用各版本的诊断TP作为分母。新增9个TP没有额外定位得分，因此35.29%不表示定位行为变差。回归、疑似新缺陷、置信度和复核信息沿用独立的原内容判定，不随P/R计分覆盖。", "",
         "| 指标 | 原Gold | TP覆盖、FP清零 | TP覆盖、保留额外FP | 定义/说明 |", "|---|---:|---:|---:|---|"]
lines += ["| " + " | ".join(r) + " |" for r in table]
lines += ["", "## 执行与产物", "", "| 项目 | 结果 |", "|---|---|", "| 修复生成、完整bundle、submission任务数 | 15 / 15 / 15 |", "| F→P / F→F / 基础设施异常 | 6 / 7 / 2 |", "| 有效执行通过率 | 6/13 = 46.15% |", "| 全部计划任务中已证实通过占比 | 6/15 = 40.00%（2题结果未知） |", "| 执行P→F回归率 | 不适用：本轮只有原始失败任务 |", "| 实际skill工具调用 | 有效13题合计1次（flink-query）；13题均有正文暴露证据 |", "| 基础设施异常任务 | jpg-ocr-stat、shock-analysis-supply；不计有效FAIL |", "", "## 评测配置", "", "| 字段 | 值 |", "|---|---|"]
for key in ("method_id", "benchmark_version", "judge_model", "reasoning_effort", "max_output_tokens", "temperature", "prompt_version", "scoring_version", "original_pass_policy", "evaluation_scope", "mode", "maximum_judge_requests", "confidence_threshold", "confidence_policy", "regression_basis", "status"):
    lines.append(f"| {key} | {summary[key]} |")
lines += ["", "SkillAxe诊断/修复与任务重跑使用Claude Opus 4.7；裁判为GPT-5.5 medium。原始轨迹复用。上表37个低置信项与5个疑似新缺陷项构成42个复核提示；阻塞项为0。", "", "来源：原gold-evaluation/summary.json、details.json和outcome-adjusted/scores.json。每个数值均保留原始全精度；显示百分比采用四舍五入至两位小数。", ""]
(OUT / "complete-report.md").write_text("\n".join(lines), encoding="utf-8")
(OUT / "complete-scores.json").write_text(json.dumps({"versions": versions, "location_policy": "retain original location_correct_count; divide by version-specific diagnosis TP", "other_judgments_policy": "retain original regression/confidence/review judgments"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
assert set(summary["metrics"]) == set(versions["pass_task_full_credit"]["metrics"])
print(json.dumps({k: v["metrics"] for k, v in versions.items()}, indent=2))
