# Batch Diagnoses

## Task data-to-d3 (reward: 0.0)

<label>Output path contract violated</label>

1) **First observable failure**
- The produced web app artifacts were written under the task output sandbox (e.g., `output/...`), but the task specification (and verifier) expects them at the absolute locations under `/root/output/...`. This mismatch causes the verifier to treat required files as missing.

2) **Trajectory step that produced it**
- The first time the agent created the deliverables (index + js/css + copied data), it wrote them into a project-relative `output/` directory instead of `/root/output/`. This is the earliest point where the eventual failure becomes inevitable (even if the HTML/JS logic were otherwise correct).

3) **Relevant skill rule or missing rule**
- Missing/insufficient rule in the D3 webapp skill: **“Honor absolute output paths exactly as specified; do not substitute project-relative paths.”**
- Many skills assume “write to `./output`” by convention; here the contract explicitly mandates `/root/output/...`.

4) **General corrective behavior**
- When a task specifies absolute filesystem destinations, always:
  - Create and write files to those exact absolute paths (e.g., `/root/output/index.html`, `/root/output/js/...`).
  - Copy input data into the exact required absolute directory (`/root/output/data/...`).
  - In `index.html`, reference assets with **relative URLs** (`js/visualization.js`, `css/style.css`, `data/...`) but ensure the **filesystem locations** match the required absolute output tree.
- Add a final self-check step: programmatically verify the existence of every required path before finishing (e.g., `test -f /root/output/index.html`, etc.). This is skill-controllable and prevents silent path mismatches.

Evidence:
- trace: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/data-to-d3/iter_1/trace.jsonl
- assessment: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/data-to-d3/iter_1/assessment.json
- workspace: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/data-to-d3/workspace
