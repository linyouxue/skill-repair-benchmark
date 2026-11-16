# Diagnosis Report: skillopt / exceltable-in-ppt

## 1. 诊断修复前轨迹
- baseline_result: `/Users/elsie/Desktop/SkillOpt-eva/experiments/gpt52-4task-unhealthy-rerun-evidencefix-v3-20261018/baseline/original-skill/exceltable-in-ppt/benchmark_result.json`
- baseline comparable/pass: `False` / `False`
- baseline error category: `None`
- rollout_dir: `/Users/elsie/Desktop/SkillOpt-eva/experiments/gpt52-4task-unhealthy-rerun-evidencefix-v3-20261018/jobs/baseline-original-skill/exceltable-in-ppt-original-skill-v11x-20260907-guarddiag-r001`

## 2. 诊断定位的 skill，以及如何修复
- overall diagnosis: The failure was caused by incomplete handling of embedded Excel workbooks inside a PPTX. The workflow updated the direct USD→CNY value but did not reliably preserve or refresh dependent values and cached formula results in the embedded XLSX, causing verifier extraction to see NaNs in inverse or unrelated cells. The current skills under-specify safe editing of embedded workbooks, formula/cache behavior after programmatic edits, validation of inverse FX cells, and post-save verification using value-based extraction paths.
- diff: `/Users/elsie/Desktop/SkillOpt-eva/experiments/gpt52-4task-unhealthy-rerun-evidencefix-v3-20261018/methods/skillopt/exceltable-in-ppt/diff.patch`
- `pptx/SKILL.md` diagnosed=True confidence=high
  - diagnosis: The skill explains where embedded workbooks reside in PPTX files but lacks concrete guidance for safely editing embedded XLSX content and validating the result. It does not clearly instruct agents to locate embeddings via slide relationship files, map slide content to workbook cells, preserve workbook integrity during re-packaging, handle direct/inverse FX pairs, or verify that downstream extraction still returns numeric values instead of NaNs after modification.
  - repair: Add a dedicated section for editing embedded Excel workbooks inside PPTX files. Instruct agents to: locate the embedded workbook through ppt/slides/_rels/*.rels; map nearby slide text to workbook cells; update both direct and inverse FX cells when appropriate; preserve formulas if inverse cells are formula-driven; repackage the PPTX without altering unrelated ZIP entries/metadata; and validate the final PPTX by re-extracting the embedded workbook and checking both formula definitions and value-based extraction outputs for unexpected blanks or NaNs.
  - change_summary: ['insert_after:applied_insert_after', 'insert_after:applied_insert_after', 'insert_after:applied_insert_after']
  - diff_stats: {'added_lines': 193, 'removed_lines': 0}
- `xlsx/SKILL.md` diagnosed=True confidence=high
  - diagnosis: The skill emphasizes preserving formulas and workbook structure but does not adequately cover recalculation and cached-value behavior after programmatic edits with libraries such as openpyxl. In this task, formulas were preserved but cached or computed values were not usable to the verifier, leading dependent cells to appear as NaN. The guidance also lacks explicit instructions for safely updating existing FX tables and verifying inverse-rate consistency.
  - repair: Expand spreadsheet-editing guidance to cover formula recalculation and cached values. Document that openpyxl preserves formulas but does not recalculate workbook results or reliably refresh cached values. Recommend workflows that either use a recalculating engine or explicitly update required non-formula dependent cells while preserving formulas. Add instructions to modify only target cells, preserve all workbook structures/styles/types, avoid rewriting whole ranges, and verify after save by reopening the workbook and checking that expected numeric cells—including inverse FX rates and unaffected cells—remain numeric and non-NaN under value-based extraction.
  - change_summary: ['insert_after:applied_insert_after', 'insert_after:applied_insert_after', 'insert_after:applied_insert_after', 'replace:applied_replace']
  - diff_stats: {'added_lines': 72, 'removed_lines': 3}

## 3. 是否修复成功及原因
- comparable/pass: `True` / `True`
- skill_exposure_verified: `True`
- outcome_category: `repair_success`
- analysis: The method-skill run is comparable and passed the task verifier.

## 4. 修复时间及成本开销
- optimizer total tokens: `3611`
- optimizer duration sec: `9.198`
- baseline evaluation: `{'wall_time_sec': 1954.1, 'cost_usd': 0.32360825, 'provider_requests': 26, 'agent_iterations': 26, 'termination_reason': 'end_turn'}`
- method evaluation: `{'wall_time_sec': 1542.3, 'cost_usd': 0.96122075, 'provider_requests': 18, 'agent_iterations': 16, 'termination_reason': 'end_turn'}`
- known_total_cost_usd: `1.284829`
