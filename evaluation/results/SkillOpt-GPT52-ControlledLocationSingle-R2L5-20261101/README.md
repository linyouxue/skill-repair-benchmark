# GPT-5.2 SkillOpt controlled R2L5 experiment

This is a new, isolated rerun of the controlled location/single experiment.
It does not overwrite or reuse candidates, diagnoses, trajectories, or scores
from `gpt52-skillopt-controlled-location-single-v1-20261026` or any Opus run.

Method label: `skillopt-controlled-oracle-hint-r2l5-v2`.

- repair model: `ai360/openai/gpt-5.2`
- diagnosis samples per round: N=3
- diagnosed-file and bounded-edit budget: L=5
- repair rounds: R=2
- round 2 starts from the round-1 candidate
- both rounds receive the same organizer location hint and no execution failure trajectory
- same-task repair gate: disabled
- shared/cross-trial diagnosis cache: disabled
- one final candidate per trial

The prior R1L4 experiment remains the frozen comparison condition. Formal
results from the two experiment roots must be reported separately.

## Artifact map

- `inputs/<dataset>/<trial>/`: independently isolated organizer inputs
- `repair_traces/<dataset>/<trial>/<attempt>/round-001/`: first-round trace and intermediate candidate
- `repair_traces/<dataset>/<trial>/<attempt>/round-002/`: second-round trace
- `candidates/<dataset>/<trial>/<attempt>/`: final round-2 candidate
- `prepared/repaired/...`: evaluator inputs made from final candidates
- `eval_runs/repaired/...`: OpenHands trajectories and verifier results
- `summaries/...`: audits and scorecards for this R2L5 experiment only
