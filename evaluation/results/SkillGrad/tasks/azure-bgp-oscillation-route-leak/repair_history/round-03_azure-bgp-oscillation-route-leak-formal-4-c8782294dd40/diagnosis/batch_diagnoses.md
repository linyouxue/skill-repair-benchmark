# Batch Diagnoses

## Task azure-bgp-oscillation-route-leak (reward: 0.0)

<label>Missing required output artifact</label>

(1) First observable failure:
- No required deliverable JSON was produced at the harness path. The output inventory contains only environment files and does not include `/app/output/oscillation_report.json`, indicating the agent never wrote the report the grader expects.

(2) Trajectory step that produced it:
- The finalization/end-turn step: the agent terminated without executing the “write result to `/app/output/oscillation_report.json` and verify by reading it back” action. This is observable from the run ending normally (“execution_ok”: true, “termination_reason”: “end_turn”) but with no output artifact present.

(3) Relevant skill rule or missing rule:
- Relevant rule exists in the skill (“Hard gate … write the required deliverable JSON to the exact harness path and verify it by reading it back.”). The failure is noncompliance with this hard gate, not a missing rule.

(4) General corrective behavior:
- Before ending, always: load the specified inputs, compute detections/evaluations, then serialize exactly the required schema to the exact required filesystem path, and confirm the file exists and is valid JSON by reading it back. If any step cannot be performed (missing inputs, path issues), explicitly handle it and do not terminate until the artifact is correctly written or the issue is surfaced.

Evidence:
- trace: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/azure-bgp-oscillation-route-leak/iter_2/trace.jsonl
- assessment: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/azure-bgp-oscillation-route-leak/iter_2/assessment.json
- workspace: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/azure-bgp-oscillation-route-leak/workspace
