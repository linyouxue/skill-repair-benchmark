# SkillHone result bundle

This directory contains the five tasks that actually entered the SkillHone
diagnosis-and-repair workflow in this campaign.  Each task contains:

- `repaired_skill/`: the complete bundle exposed to the final recorded
  method-skill rollout;
- `original_run/`: the archived historical Original-Skill run;
- `repaired_run/`: the final selected method-skill rollout, including the
  executor request, result, verifier artifacts, and raw trajectories.

## Results

| Task | Final recorded verifier result |
| --- | --- |
| dialogue-parser | PASS |
| software-dependency-audit | PASS |
| python-scala-translation | PASS |
| video-silence-remover | FAIL |
| sec-financial-report | FAIL |

`python-scala-translation` was verified using the same final bundle through
the `vllm-fallback-retry` route after the OpenRouter route was unavailable.
Its `repaired_run/executor_request.json` therefore truthfully records
`method_id: vllm-fallback-retry`; the primary SkillHone executor artifacts use
`method_id: skillhone-v2`, which is the `submission.json` method identifier.
The bundles are byte-identical for the exposed Skill files.  A future unified
scoring run should rerun that task under `skillhone-v2` if strict executor
method-ID matching is required.

This is a partial campaign artifact: `exoplanet-detection-period` was paused
at the owner's request and is intentionally absent; `paratransit-routing` did
not enter this diagnosis/repair campaign.  Consequently this `submission.json`
has the required schema but is not a complete seven-task Core-25 submission.

All copied `result.json`, `benchmark_result.json`, and trajectory files are
unaltered executor artifacts.  The generated Markdown timeline files under
`trajectory_timelines/` are derived from those raw trajectories.

The archive contains 26 exportable ACP trajectories: five Original-Skill
`before` trajectories and 21 method-skill `after` trajectories. The first
Python/Scala candidate has no ACP trajectory file in its original executor
artifact, so there is no model trajectory to convert for that one run.
