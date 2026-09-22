# Batch Diagnoses

## Task azure-bgp-oscillation-route-leak (reward: 0.0)

<label>Missing required output write</label>

(1) First observable failure:
No required deliverable was produced: the output inventory contains only environment files and **does not include** `/app/output/oscillation_report.json`. This is the earliest concrete, externally observable mismatch with the task requirements (write JSON report to a specific path).

(2) Trajectory step that produced it:
The agent ended the run (`end_turn`) without creating/verifying the on-disk report. In the trace, there are tool calls but no step that writes to `/app/output/oscillation_report.json` and no subsequent read-back verification; the run terminates immediately after those non-writing actions.

(3) Relevant skill rule or missing rule:
The preloaded `azure-bgp` skill explicitly includes a **hard gate**: “deliverable write + read-back verification … DO NOT end the run until the read-back verification succeeds.” The agent violated this rule by finishing without writing and verifying the output JSON at the required path.

(4) General corrective behavior:
Before ending, always (a) construct the report JSON with required keys, (b) write it to the exact harness path, and (c) read it back to confirm existence, non-empty content, and valid JSON schema. If the file is missing or parse fails, correct the path/payload and re-write. This is fully skill-controllable (not an API/dependency/grader issue).

Evidence:
- trace: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/azure-bgp-oscillation-route-leak/iter_4/trace.jsonl
- assessment: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/azure-bgp-oscillation-route-leak/iter_4/assessment.json
- workspace: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/azure-bgp-oscillation-route-leak/workspace
