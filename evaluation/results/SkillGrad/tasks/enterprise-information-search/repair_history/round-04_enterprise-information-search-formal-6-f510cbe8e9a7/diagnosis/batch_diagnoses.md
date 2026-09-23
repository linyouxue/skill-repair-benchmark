# Batch Diagnoses

## Task enterprise-information-search (reward: 0.0)

<label>Missing required output artifact</label>

(1) **First observable failure:** The run ends (`termination_reason: end_turn`, `execution_ok: true`) but the required deliverable **`/root/answer.json` is not produced/validated** (and thus the verifier cannot find a schema-correct answers file). This is the earliest externally observable failure because the task’s success condition is the presence of that JSON with all question keys and token counts.

(2) **Trajectory step that produced it:** The **final agent message / termination step** (end of the single conversation run) where the agent stops without performing the “write → read-back → schema validate” completion gate and without writing `/root/answer.json`.

(3) **Relevant skill rule or missing rule:** The preloaded skill **`enterprise-artifact-search`** contains an explicit **“Finalize (Required): hard completion gate (block termination)”** rule: *“Do not end the run until the required output artifact is written and validated… treat file-write + read-back validation as the last action in the run.”* The run shows **0 skill invocations**, and the completion gate was not executed. This is a **skill-controllable** failure (not an API/dependency/permission issue).

(4) **General corrective behavior:** Before terminating, always execute a mandatory completion routine:
- read `/root/question.txt`, compute answers by searching `/root/DATA`,
- write `/root/answer.json` with **all q-keys**, each having `{"answer": [..], "tokens": <int>}`,
- immediately **read back** the file and assert schema invariants (top-level dict, every `answer` is a list, every `tokens` is an int, all questions covered). Only then end the run.

Evidence:
- trace: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/enterprise-information-search/iter_5/trace.jsonl
- assessment: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/enterprise-information-search/iter_5/assessment.json
- workspace: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/enterprise-information-search/workspace
