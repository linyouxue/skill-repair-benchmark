"""Offline sensitivity analysis; does not modify or rerun the Gold evaluation."""
import json
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def score(tp, fp, fn):
    return dict(tp=tp, fp=fp, fn=fn,
                precision=tp / (tp + fp) if tp + fp else None,
                recall=tp / (tp + fn) if tp + fn else None,
                f1=2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None)


details = read(ROOT / "gold-evaluation/details.json")
summary = read(ROOT / "gold-evaluation/summary.json")
manifest = read(ROOT / "manifest.json")
baseline = {t["task_id"]: t for t in manifest["tasks"]}
rows = []
for task in details["tasks"]:
    tid = task["task_id"]
    result_path = ROOT / "runs" / manifest["method_id"] / f"{tid}-skillaxe-opus47-r001/benchmark_result.json"
    result = read(result_path)
    assert result["task_id"] == tid
    assert baseline[tid]["status"] == "FAIL"
    outcome = ("INFRA_ERROR" if not result["execution_ok"] or result["task_passed"] is None
               else "PASS" if result["task_passed"] else "FAIL")
    n = task["gold_defect_count"]
    original = {k: task["metrics"][k] for k in ("diagnosis", "repair")}
    assert all(m["tp"] + m["fn"] == n for m in original.values())
    full = original.copy()
    retain_extra = original.copy()
    if outcome == "PASS":
        full = {k: score(n, 0, 0) for k in original}
        retain_extra = {
            "diagnosis": score(n, original["diagnosis"]["fp"], 0),
            "repair": score(n, task["metrics"]["harmful_extra_repair_count"], 0),
        }
    rows.append(dict(task_id=tid, baseline="FAIL", outcome=outcome, gold_defect_count=n,
                     result_path=str(result_path.relative_to(ROOT)), original=original,
                     pass_task_full_credit=full, gold_tp_keep_extra_fp=retain_extra))

aggregates = {}
for version in ("original", "pass_task_full_credit", "gold_tp_keep_extra_fp"):
    aggregates[version] = {}
    for kind in ("diagnosis", "repair"):
        counts = [sum(r[version][kind][k] for r in rows) for k in ("tp", "fp", "fn")]
        aggregates[version][kind] = score(*counts)
        assert counts[0] + counts[2] == summary["total_gold_defect_count"]
        if version == "original":
            assert all(aggregates[version][kind][k] == summary["metrics"][kind][k]
                       for k in ("tp", "fp", "fn"))

rules = {
    "pass_task_full_credit": "F→P任务：诊断和修复均设TP=Gold defect数量、FP=FN=0；其他任务保留原Gold评分。",
    "gold_tp_keep_extra_fp": "F→P任务：全部Gold defect设为TP、FN=0；保留原诊断额外误报FP及修复有害额外改动FP，移除被覆盖的Gold修复失败FP；其他任务保持原分。",
    "scope": "仍统计15题32个Gold defect；2个基础设施异常任务保留原内容评分，不将其视为执行FAIL或PASS。",
    "limitations": "离线事后替代计分，不是Gold裁判重新认定。通过不证明逐项诊断正确或全部缺陷均被修复。定位、回归、置信度指标不重新推断。",
}
payload = dict(method_id=manifest["method_id"], source_details="gold-evaluation/details.json",
               source_summary="gold-evaluation/summary.json", rules=rules,
               task_count=len(rows), total_gold_defect_count=sum(r["gold_defect_count"] for r in rows),
               execution_outcomes=dict(Counter(r["outcome"] for r in rows)),
               overridden_task_count=sum(r["outcome"] == "PASS" for r in rows),
               overridden_gold_defect_count=sum(r["gold_defect_count"] for r in rows if r["outcome"] == "PASS"),
               metrics=aggregates, tasks=rows)
(OUT / "scores.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = ["# F→P 任务全 TP：替代计分", "", "现有 Gold 评分保留不变；本文件仅基于已完成结果离线重算，无模型调用、无任务重跑。", ""]
lines += [f"- {value}" for value in rules.values()]
lines += ["", "6个F→P任务覆盖12个Gold defect。诊断TP由原来的3个覆盖为12个，净增9个；修复TP由1个覆盖为12个，净增11个。", "",
          "## 汇总（micro）", "", "| 口径 | 指标 | TP | FP | FN | Precision | Recall | F1 |", "|---|---|---:|---:|---:|---:|---:|---:|"]
labels = {"original": "原Gold评分", "pass_task_full_credit": "新版：通过任务整体满分", "gold_tp_keep_extra_fp": "附加：保留额外FP"}
for version, metrics in aggregates.items():
    for kind, m in metrics.items():
        lines.append(f"| {labels[version]} | {'诊断' if kind == 'diagnosis' else '修复'} | {m['tp']} | {m['fp']} | {m['fn']} | {m['precision']:.2%} | {m['recall']:.2%} | {m['f1']:.2%} |")
lines += ["", "## 逐题核对", "", "计数均为TP/FP/FN。INFRA_ERROR仅表示执行无有效结论，内容评分仍在15题汇总内。", "",
          "| 任务 | 验证 | Gold缺陷数 | 原诊断 | 新诊断 | 原修复 | 新修复 |", "|---|---|---:|---|---|---|---|"]
for r in rows:
    values = []
    for kind in ("diagnosis", "repair"):
        for version in ("original", "pass_task_full_credit"):
            m = r[version][kind]
            values.append(f"{m['tp']}/{m['fp']}/{m['fn']}")
    lines.append(f"| {r['task_id']} | {r['outcome']} | {r['gold_defect_count']} | " + " | ".join(values) + " |")
lines += ["", "数据来源：`../gold-evaluation/details.json`、`../gold-evaluation/summary.json`、`../manifest.json`、各任务真实`benchmark_result.json`。", "",
          "`scores.json`包含两种替代口径的逐题明细与源结果路径。运行`python recalculate.py`可离线复算。", ""]
(OUT / "report.md").write_text("\n".join(lines), encoding="utf-8")
print(json.dumps({k: v for k, v in payload.items() if k != "tasks"}, ensure_ascii=False, indent=2))
