# Batch Diagnoses

## Task dynamic-object-aware-egomotion (reward: 0.0)

LABEL: Missing artifact generation

1) First observable failure:
No required output artifacts were produced: neither the motion-label JSON nor the dynamic-mask NPZ exists in the output inventory (it contains only the input video). This is the earliest concrete mismatch with the task requirements.

2) Trajectory step that produced it:
The final agent message / termination (“end_turn”) occurred without any tool-driven execution that reads the video, samples frames at 5 fps, estimates egomotion, builds masks, and writes the two files to the required /root paths. In the trace summary, only 3 tool calls occurred and no skills were invoked; none resulted in creating `/root/pred_instructions.json` or `/root/pred_dyn_masks.npz`.

3) Relevant skill rule or missing rule:
Skill-controllable. The loaded skills include “sampling-and-indexing”, “egomotion-estimation”, “dyn-object-masks”, and “output-validation”, but the run shows **0 skill invocations**. The missing/ignored rule is effectively: *must invoke the pipeline skills and then run output-validation to ensure the two required files exist at the correct absolute paths before finishing.*

4) General corrective behavior:
Always execute the full pipeline before ending the turn:
- Sample the video at the specified fps and establish sampled-frame indices.
- Compute interval-to-label mapping covering all sampled frames and write the JSON in the specified half-open interval format.
- Produce one binary dynamic-object mask per sampled frame, encode in CSR keys plus `shape`, and save NPZ.
- Validate existence, keys, shapes, and index coverage (including that every sampled frame has a mask) before returning. If validation fails, do not finish; fix and re-save outputs.

Evidence:
- trace: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/dynamic-object-aware-egomotion/iter_1/trace.jsonl
- assessment: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/dynamic-object-aware-egomotion/iter_1/assessment.json
- workspace: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/dynamic-object-aware-egomotion/workspace
