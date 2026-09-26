# SkillAxe / Claude Opus 4.7 / Gold 15

Updated 2026-09-26: **7 PASS, 8 FAIL, 0 infrastructure errors; verified fix rate 7/15 = 46.67%.** Original trajectories, all 15 repaired bundles, and the existing content judgments are reused except that the selected `jpg-ocr-stat` execution is replaced by the valid corrected-budget fresh rollout described below.

The reported outcome-adjusted rule is: for each valid F→P task, set diagnosis and repair TP to its Gold-defect count and FP/FN to zero. All other tasks retain their content-judge scores. This is a scoring override, not a claim that the judge independently confirmed every defect. Location keeps the judged hit count divided by the adjusted TP; regression, confidence and review judgments remain independent.

- [Complete metric table](outcome-adjusted/complete-report.md), [per-task comparison](outcome-adjusted/report.md), and machine-readable `scores.json` / `complete-scores.json`.
- `gold-evaluation/`: GPT-5.5 medium content judgments remain unchanged. This update changes the execution-grounded Verified Fix fields from 6/15 to **7/15** and applies the established F→P override; no new content-judge request was made.
- `tasks/<task_id>/repaired_run/`: latest selected execution. For `jpg-ocr-stat`, the selected run is now `jpg-ocr-stat-skillaxe-opus47-r004-budget65`.
- JPG r002 reached its **actual 60-iteration limit** and failed. After the budget was corrected to **65**, a fresh r004 reused the exact same SkillAxe repaired bundle (bundle SHA-256 `109c28b269e353af736900ef3c13fd53d448c0d94ee0b447d9dfd05f3ff343ab`) and completed normally after **27 iterations / 27 provider requests**, `termination_reason=end_turn`, with the official verifier **1/1 PASS** and reward **1.0**.
- An intermediate r003 budget-65 launch was infrastructure-invalid because the host-side foreground MCP command was terminated by its 600-second command timeout while leaving an orphan task container. That run is not scored and is not the selected execution.
- Shock r002 remains FAIL at 60 iterations. Its trajectory shows online data access difficulties and eventual successful PWT/IMF retrieval; it did not finish the required workbook. See `trajectory-audit.json` for the historical r002 audit scope and limitations.
- The selected JPG r004 has **0 native skill invocations** but full persistent Skill-context injection was verified; `skill_exposure_verified=true`, with all five Skill bodies preloaded. Across all 15 runs, invocation count is reported separately from content exposure.
- `history/pre-retry-20260922/` preserves earlier scores/state/error summaries. Previous selected JPG runs also remain recoverable from Git history. `recovery-evidence/` preserves the prior verifier-only recovery evidence; it is historical and does not override the fresh r004 PASS.
- `protocol.json` records the budget correction. Repair and execution use Opus 4.7, 32768 output tokens, with temperature/effort/thinking fields omitted; the judge uses GPT-5.5 medium, 8192 output tokens, temperature omitted. Omitted fields are not proof that provider-side thinking was disabled.
- The canonical selected ACP trajectory is `tasks/jpg-ocr-stat/repaired_run/trajectory/acp_trajectory.jsonl`; the readable deterministic export is under `trajectory_timelines/after/`. The r004 raw provider trace is stored uncompressed as `trajectory/llm_trajectory.jsonl` (about 22.9 MB, below GitHub's per-file limit), together with the r004 `results.jsonl` and pre-verifier artifact. The stale r002 compressed provider trace was removed, so `compressed-trajectories.json` is now empty.

Recalculate all reported scores without model requests:

```sh
python evaluation/results/SkillAxe-Opus47-Gold15-20260921/outcome-adjusted/recalculate.py
python evaluation/results/SkillAxe-Opus47-Gold15-20260921/outcome-adjusted/complete_report.py
```

Original baseline output limits differ on six tasks (128000), and the original JPG baseline used 65 iterations; this historical conditional-on-failure comparison retains those facts. All current task outcomes have a real verifier result; valid execution does not imply identical historical budgets.

