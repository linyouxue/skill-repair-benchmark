# Remote upload scope

This directory is the isolated remote copy of the GPT-5.2 SkillOpt controlled
location/single-repair experiment
`gpt52-skillopt-controlled-location-single-r2l5-v2-20261027`.

Included:

- final summaries, scorecard, semantic review, and audits;
- repair inputs, candidates, and complete repair traces;
- repaired and control native-evaluation runs, including OpenHands trajectories,
  verifier artifacts, run records, and invalid attempts retained for audit;
- terminal logs, experiment configuration, runner commands, protocol, and code
  snapshot.

Intentionally omitted:

- `prepared/` (about 2.0 GB): reproducible benchmark staging copies containing
  repeated task packages, SEC archives, and video inputs. These are execution
  inputs rather than results or trajectories and can be regenerated from the
  recorded candidates, configurations, and dataset package.
- local caches and `__pycache__` directories.

The experiment is GPT-5.2-only. No Opus 4.7 result directory or trajectory is
included in this upload.
