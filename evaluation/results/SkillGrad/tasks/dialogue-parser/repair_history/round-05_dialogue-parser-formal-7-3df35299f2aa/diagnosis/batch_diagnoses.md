# Batch Diagnoses

## Task dialogue-parser (reward: 0.667)

<label>Missing required filesystem artifacts</label>

1) **First observable failure**
- The run finished with **no required output artifacts** produced: neither `/app/dialogue.json` nor `/app/dialogue.dot` exists in the output inventory (only `script.txt` is present). This violates the task’s explicit deliverables requirement and prevents the verifier from validating the graph.

2) **Trajectory step that produced it**
- The **finalization / end-of-run step**: the agent terminated (`end_turn`) without exporting the parsed graph and without an artifact existence/reload check. This is the first point where the failure becomes observable (missing files).

3) **Relevant skill rule or missing rule**
- Directly covered by the preloaded skill’s **“Plan the run” hard stop** and **“End-of-run guardrail”**:
  - “immediately before `end_turn`, run export → artifact check … Do not call `end_turn` until you have re-opened the required files and confirmed they load/parse.”
- Also implicated: “Common Pitfalls: Finishing logic but not materializing required deliverables”.

4) **General corrective behavior**
- Before terminating, always:
  - **Export** the in-memory graph to the exact required paths (`/app/dialogue.json`, `/app/dialogue.dot`).
  - Perform an **artifact check**: confirm both files exist, are non-empty, and can be re-opened (JSON loads successfully; DOT contains a valid `digraph` header).
  - Only then end the run.
- This is **skill-controllable** (not an API/dependency/grader issue): it’s a missing write/verify step, not an external failure.

Evidence:
- trace: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/dialogue-parser/iter_6/trace.jsonl
- assessment: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/dialogue-parser/iter_6/assessment.json
- workspace: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/dialogue-parser/workspace
