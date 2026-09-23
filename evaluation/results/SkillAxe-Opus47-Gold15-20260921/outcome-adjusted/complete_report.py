"""Expand the offline comparison to every evaluator summary metric."""
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent
def read(p):
    return json.loads(p.read_text(encoding="utf-8-sig"))
def pct(v):
    if v is None:
        return "N/A"
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
        m["location_accuracy"] = m["location_correct_count"] / m["diagnosis"]["tp"] if m["diagnosis"]["tp"] else None
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
    "location_accuracy": "保留内容裁判定位命中数/本列诊断TP",
    "failed_gold_repair_count": "尝试修复但未正确完成的Gold缺陷；覆盖口径移除通过任务的对应项",
    "harmful_extra_repair_count": "有害或无依据的额外改动；整体覆盖口径移除通过任务的对应项",
    "substantively_modified_bundles": "存在实质修改的bundle数，沿用内容判定",
    "regressed_bundles": "内容裁判判为引入新缺陷的bundle数，沿用原判",
    "regression_rate": "发生回归的bundle/实质修改bundle；不是执行P→F率",
    "regression_count": "回归新缺陷数量，沿用原判",
    "possible_new_defect_count": "额外改动中的疑似新缺陷数；与回归计数不直接相加",
}
for key, note in notes.items():
    vals = [v["metrics"][key] for v in versions.values()]
    row(key, [pct(v) for v in vals] if key in ("location_accuracy", "regression_rate") else vals, note)
for key in ("task_count", "total_gold_defect_count", "evaluated_task_count", "evaluated_gold_defect_count", "scored_task_count", "skipped_original_pass_task_count", "skipped_gold_defect_count", "skipped_original_pass_rate", "confidence_task_count", "total_judgment_count", "low_confidence_count", "low_confidence_rate", "review_item_count", "blocking_review_count"):
    value = pct(summary[key]) if key.endswith("rate") else summary[key]
    row(key, [value] * 3, "合并内容评测：2题新裁判，13题复用；计分覆盖不改独立判断")
for key, value in summary.items():
    if key.startswith("verified_fix_"):
        value = pct(value) if key in ("verified_fix_rate", "verified_fix_coverage") else value
        row(key, [value] * 3, "新版评测器直接核验的执行指标；不随内容计分覆盖")

lines = ["# 完整指标对照", "", "三列依次为原Gold评分、F→P任务TP覆盖且FP/FN清零、F→P的Gold缺陷全部计TP但保留额外FP。后两者均为离线替代统计，不是新的Gold裁判结果。", "",
         "定位保留内容裁判location_correct判定，并使用各版本的诊断TP作为分母。覆盖增加的TP不会自动增加定位命中。回归、疑似新缺陷、置信度和复核信息沿用独立的内容判定，不随P/R计分覆盖。", "",
         "| 指标 | 原Gold | TP覆盖、FP清零 | TP覆盖、保留额外FP | 定义/说明 |", "|---|---:|---:|---:|---|"]
lines += ["| " + " | ".join(r) + " |" for r in table]
counts = scores['execution_outcomes']
npass, nfail, ninfra = [counts.get(k, 0) for k in ('PASS','FAIL','INFRA_ERROR')]
runs = [read(ROOT / 'tasks' / t['task_id'] / 'repaired_run/result.json') for t in scores['tasks']]
invocations = sum(r.get('n_skill_invocations') or 0 for r in runs)
exposed = sum(read(ROOT / 'tasks' / t['task_id'] / 'repaired_run/benchmark_result.json').get('skill_exposure_verified') is True for t in scores['tasks'])
lines += ["", "## 执行与产物", "", "| 项目 | 结果 |", "|---|---|",
          f"| 完整bundle / submission任务数 | {len(runs)} / {len(runs)} |",
          f"| F→P / F→F / 基础设施异常 | {npass} / {nfail} / {ninfra} |",
          f"| 有效执行通过率 | {npass}/{npass+nfail} = {pct(npass/(npass+nfail))} |",
          f"| 全部计划任务中已证实通过占比 | {npass}/{len(runs)} = {pct(npass/len(runs))} |",
          "| 执行P→F回归率 | 不适用：本轮只有原始失败任务 |",
          f"| 实际skill工具调用 / 正文暴露任务数 | {invocations} / {exposed} |",
          "| JPG补跑 | r002真实预算60，达到迭代上限；只恢复原XLSX的verifier，未再调用模型。后续jpg预算已改65，历史记录不改写。 |",
          "| 裁判新增调用 | 仅jpg与shock：4个有效响应；另有1次入站429拒绝，成功响应未重复调用。 |",
          "", "## 评测配置", "", "| 字段 | 值 |", "|---|---|"]
for key in ("method_id", "benchmark_version", "judge_model", "reasoning_effort", "max_output_tokens", "temperature", "prompt_version", "scoring_version", "original_pass_policy", "evaluation_scope", "mode", "maximum_judge_requests", "confidence_threshold", "confidence_policy", "regression_basis", "status"):
    lines.append(f"| {key} | {summary[key]} |")
lines += ["", "SkillAxe诊断/修复与任务重跑使用Claude Opus 4.7；裁判为GPT-5.5 medium。原始轨迹、修复bundle与其他13题内容裁判均复用。", "", "来源：gold-evaluation/summary.json、details.json和outcome-adjusted/scores.json；evaluation-provenance.json记录裁判复用。每个数值保留全精度；显示百分比四舍五入至两位小数。", ""]
(OUT / "complete-report.md").write_text("\n".join(lines), encoding="utf-8")
(OUT / "complete-scores.json").write_text(json.dumps({"versions": versions, "location_policy": "retain original location_correct_count; divide by version-specific diagnosis TP", "other_judgments_policy": "retain original regression/confidence/review judgments"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
assert set(summary["metrics"]) == set(versions["pass_task_full_credit"]["metrics"])
print(json.dumps({k: v["metrics"] for k, v in versions.items()}, indent=2))
