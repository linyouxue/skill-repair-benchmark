# Batch Diagnoses

## Task jpg-ocr-stat (reward: 0.0)

<label>Wrong output location written</label>

(1) First observable failure:
The expected deliverable `/app/workspace/stat_ocr.xlsx` was not produced in the run outputs (the artifact is missing), so the verifier cannot line-by-line compare the Excel content.

(2) Trajectory step that produced it:
The file-writing step saved the spreadsheet to a different path than required (e.g., a relative `workspace/...` location or another working directory), so the harness did not find it at the mandated absolute path.

(3) Relevant skill rule or missing rule:
Missing/violated rule in the XLSX-writing workflow skill: “Always write final artifacts to the exact absolute path specified by the task and verify existence after write.”  
This is skill-controllable (not an API/permission/dependency/grader issue).

(4) General corrective behavior:
When generating deliverables, always:
- write to the exact required absolute path (no relative-path substitutions),
- create parent directories if needed,
- immediately `stat()`/open the file after saving to confirm it exists and is readable,
- only then finish (and avoid writing additional copies elsewhere).

Evidence:
- trace: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/jpg-ocr-stat/iter_4/trace.jsonl
- assessment: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/jpg-ocr-stat/iter_4/assessment.json
- workspace: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/jpg-ocr-stat/workspace
