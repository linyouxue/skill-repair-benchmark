# Batch Diagnoses

## Task jpg-ocr-stat (reward: 0.0)

<label>Missing output file creation</label>

(1) First observable failure:
No output artifact was produced at all (output inventory is empty). The task requires creating `/app/workspace/stat_ocr.xlsx` with a single sheet "results" and 3 columns; instead, nothing was written.

(2) Trajectory step that produced it:
The failure is attributable to the finalization phase of the run (end of trajectory), where the agent should have executed the write-to-Excel step. The run terminates as “stuck” and never reaches a successful “save workbook to required path” action, so the first observable failure is the absence of the Excel export.

(3) Relevant skill rule or missing rule:
Missing (or not followed) skill rule: “Always produce the required output file at the exact specified path and schema before termination; verify file existence and sheet/columns.”  
If such a rule exists, it was not applied; if it does not exist, it is a gap in the workflow skill (OCR → parse → dataframe → Excel export with strict schema checks).

(4) General corrective behavior:
Add/execute a mandatory “output contract” step:
- After extraction/parsing, always write the Excel file to the exact required location with exactly one sheet named "results" and only the required columns.
- Immediately validate: file exists, sheet count/name correct, header matches, row order by filename, and no extra rows/columns.
- If validation fails, fix and re-export rather than continuing to iterate on OCR.
This is skill-controllable (workflow/completion discipline), not an external API, permission, or grader issue.

Evidence:
- trace: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/jpg-ocr-stat/iter_0/trace.jsonl
- assessment: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/jpg-ocr-stat/iter_0/assessment.json
- workspace: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/jpg-ocr-stat/workspace
