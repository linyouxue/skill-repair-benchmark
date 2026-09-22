# Batch Diagnoses

## Task azure-bgp-oscillation-route-leak (reward: 0.0)

<label>Missing required deliverable file</label>

(1) First observable failure:
- No required on-disk output artifact was produced. The output inventory contains only environment files and **does not include** `/app/output/oscillation_report.json`, which the verifier expects.

(2) Trajectory step that produced it:
- The agent ended the run (`end_turn`) without writing the report file. This corresponds to the final agent-message/termination step in the trace where execution stops after limited tool usage and no file-write action.

(3) Relevant skill rule or missing rule:
- Skill rule violated: **“Termination guard (must pass before ending the run): deliverable write + read-back verification”**. The skill explicitly requires confirming (a) exact path written, (b) JSON parses + required keys, and (c) read-back verification succeeded. None of these were satisfied, indicating the agent did not follow the skill’s mandatory pre-termination checklist.
- Not an API/permission/harness issue: execution was OK, and the failure is controllable by the agent/skill behavior (write/verify output).

(4) General corrective behavior:
- Always implement the deliverable workflow: load inputs from `/app/data/`, compute detection + solution evaluation, then **write** the JSON to the exact required path, and **read it back** to confirm it parses and contains all required top-level keys before terminating. If any check fails, rewrite and re-verify rather than ending the run.

Evidence:
- trace: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/azure-bgp-oscillation-route-leak/iter_5/trace.jsonl
- assessment: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/azure-bgp-oscillation-route-leak/iter_5/assessment.json
- workspace: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/azure-bgp-oscillation-route-leak/workspace
