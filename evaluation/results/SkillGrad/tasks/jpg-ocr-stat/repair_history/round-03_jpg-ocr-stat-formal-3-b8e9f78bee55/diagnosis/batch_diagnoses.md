# Batch Diagnoses

## Task jpg-ocr-stat (reward: 0.0)

<label>Missing required output workbook</label>

(1) First observable failure:
- The required deliverable Excel file was not produced at the specified path (`/app/workspace/stat_ocr.xlsx`). This is the earliest concrete, externally visible violation of the output contract; without the file, the verifier cannot do the mandated line-by-line comparison.

(2) Trajectory step that produced it:
- The failure is attributable to the end of the agent run (termination with `end_turn`) without a successful “write + save + re-open validate” step for the workbook. In the trace summary, there is no evidence of creating the deliverable before completion, and the post-run outputs do not contain the expected workbook.

(3) Relevant skill rule or missing rule:
- Relevant existing rule: **xlsx/SKILL.md → “Deliverable-first control loop”** and its decision rule: *“if you have made several tool calls without creating the deliverable file, stop exploring and immediately write the skeleton workbook, then proceed.”*
- The run violated this rule by not generating the workbook early (or at all) and not validating it after saving.

(4) General corrective behavior:
- Enforce a deliverable-first workflow: immediately create `/app/workspace/stat_ocr.xlsx` with exactly one sheet named `"results"` and the exact three headers in order (`filename`, `date`, `total_amount`), then iterate on OCR/parsing to fill rows. After each update, **save to the exact path and re-open to assert**: file exists, only the `"results"` sheet is present, headers match exactly, rows are sorted by filename, and fields use required formats (ISO date, 2-decimal string) or null.
- This is skill-controllable (no evidence of API/dependency/permission/verifier malfunction); it’s a planning/execution omission relative to the xlsx skill’s contract.

Evidence:
- trace: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/jpg-ocr-stat/iter_2/trace.jsonl
- assessment: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/jpg-ocr-stat/iter_2/assessment.json
- workspace: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/jpg-ocr-stat/workspace
