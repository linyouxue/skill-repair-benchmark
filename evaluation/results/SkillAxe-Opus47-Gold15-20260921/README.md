# SkillAxe / Claude Opus 4.7 / Gold 15

Updated 2026-09-22: **6 PASS, 9 FAIL, 0 infrastructure errors; verified fix rate 6/15 = 40%.** Original trajectories, all 15 repaired bundles, and 13 existing task judgments are reused.

The reported outcome-adjusted rule is: for each valid F→P task, set diagnosis and repair TP to its Gold-defect count and FP/FN to zero. All other tasks retain their content-judge scores. This is a scoring override, not a claim that the judge independently confirmed every defect. Location keeps the judged hit count divided by the adjusted TP; regression, confidence and review judgments remain independent.

- [Complete metric table](outcome-adjusted/complete-report.md), [per-task comparison](outcome-adjusted/report.md), and machine-readable `scores.json` / `complete-scores.json`.
- `gold-evaluation/`: merged GPT-5.5 medium judgments scored offline with evaluator v1.4 and all 15 selected executor results. Only JPG and shock were rejudged (four successful new responses; one initial request was rejected with admission-control HTTP 429). Other thirteen judgments are unchanged; see `evaluation-provenance.json`.
- `tasks/<task_id>/repaired_run/`: latest selected execution; submission and PACKAGING identify r002 for the two replacements. Repaired bundles are unchanged and match the run inputs byte for byte.
- JPG r002 reached its **actual 60-iteration limit**, leaving a real `stat_ocr.xlsx`. Only the original verifier was rerun against these unchanged saved bytes in a clean original task image. It failed the value comparison. No agent rerun or reconstructed output was used. The user's subsequent **65-iteration** correction applies to future JPG runs; historical metadata remains 60.
- Shock r002 reached 60 iterations and failed eight of nine tests. Its trajectory shows online data access difficulties and eventual successful PWT/IMF retrieval; it did not finish the required workbook. See `trajectory-audit.json` for the scope and limitations of the audit.
- Both replacement trials pass the artifact validator, have complete ACP/LLM/results records, and have **0 native skill invocations** with full-SKILL context injection evidence. Across all 15 runs, invocation count is reported separately from content exposure.
- `history/pre-retry-20260922/` preserves previous scores/state/error summaries. Full previous failed trajectories remain in Git commit `4b5e642d`. `recovery-evidence/` preserves verifier recovery and the new judge responses.
- `protocol.json` records the budget correction. Repair and execution use Opus 4.7, 32768 output tokens, with temperature/effort/thinking fields omitted; the judge uses GPT-5.5 medium, 8192 output tokens, temperature omitted. Omitted fields are not proof that provider-side thinking was disabled.

JPG's 156 MB LLM JSONL is losslessly gzip-compressed to meet GitHub's individual-file limit; the raw hash/size are in `compressed-trajectories.json`. Restore it before using consumers that require an uncompressed JSONL:

```sh
python evaluation/results/SkillAxe-Opus47-Gold15-20260921/restore_large_trajectories.py
```

Recalculate all reported scores without model requests:

```sh
python evaluation/results/SkillAxe-Opus47-Gold15-20260921/outcome-adjusted/recalculate.py
python evaluation/results/SkillAxe-Opus47-Gold15-20260921/outcome-adjusted/complete_report.py
```

Original baseline output limits differ on six tasks (128000), and the original JPG baseline used 65 iterations; this historical conditional-on-failure comparison retains those facts. All current task outcomes have a real verifier result; valid execution does not imply identical historical budgets.
