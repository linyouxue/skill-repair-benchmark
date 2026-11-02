# SkillHone / GPT-5.2 xhigh

Completed controlled experiment on `skill-repair-controlled-datasets-20261020`.
Repair and task execution both use Tatu `gpt-5.2` / `xhigh`, with at most
16,384 output tokens per model request. Each input gets one native SkillHone
repair and one original-task execution per round, stopping at the first full
score or after five rounds. Three independent workers refill rolling slots.

All **22 inputs / 101 valid rounds** finished. Ordinary failures, zero rewards
and normal budget stops remain measured results. Infrastructure attempts are
excluded from valid rounds; only their identifier/reason/usage/cost briefs
remain after the user-required local cleanup.

## Results

| Condition | Inputs | Final full-score passes |
|---|---:|---:|
| Known error location | 5 | 1 |
| Single-fault leave-one-out | 12 | 2 |
| All-fault control | 5 | 0 |
| Total | 22 | 3 |

`Pass` below means the original task's official score is 1. Semantic target
repair and preservation of other working repairs have not been independently
adjudicated. A task pass alone does not establish those content-level claims.

| Input | Round rewards | Final |
|---|---|---|
| [location-dialogue-parser](final/location-dialogue-parser/skills) | 0.833 → 0 → 0 → 0 → 0 | Fail |
| [location-data-to-d3](final/location-data-to-d3/skills) | 0 → 0 → 0 → 0 → 0 | Fail |
| [location-flink-query](final/location-flink-query/skills) | 0 → 0 → 0 → 0 → 0 | Fail |
| [single-flink-query-all](final/single-flink-query-all/skills) | 0 → 0 → 0 → 0 → 0 | Fail |
| [single-flink-query-RI-001](final/single-flink-query-RI-001/skills) | 0 → 0 → 0 → 0 → 0 | Fail |
| [single-flink-query-RI-002](final/single-flink-query-RI-002/skills) | 0 → 0 → 0 → 0 → 0 | Fail |
| [location-manufacturing-equipment-maintenance](final/location-manufacturing-equipment-maintenance/skills) | 0 → 0 → 0 → 0 → 0 | Fail |
| [single-manufacturing-equipment-maintenance-all](final/single-manufacturing-equipment-maintenance-all/skills) | 0 → 0 → 0 → 0 → 0 | Fail |
| [single-manufacturing-equipment-maintenance-RI-001](final/single-manufacturing-equipment-maintenance-RI-001/skills) | 0 → 0 → 0 → 0 → 0 | Fail |
| [single-manufacturing-equipment-maintenance-RI-002](final/single-manufacturing-equipment-maintenance-RI-002/skills) | 0 → 0 → 0 → 0 → 0 | Fail |
| [location-pddl-airport-planning](final/location-pddl-airport-planning/skills) | 1 | Pass |
| [single-video-silence-remover-all](final/single-video-silence-remover-all/skills) | 0 → 0 → 0 → 0 → 0 | Fail |
| [single-video-silence-remover-RI-001](final/single-video-silence-remover-RI-001/skills) | 0 → 0 → 0 → 0 → 0 | Fail |
| [single-video-silence-remover-RI-002](final/single-video-silence-remover-RI-002/skills) | 1 | Pass |
| [single-video-silence-remover-RI-003](final/single-video-silence-remover-RI-003/skills) | 0 → 0 → 0 → 1 | Pass |
| [single-sec-financial-report-all](final/single-sec-financial-report-all/skills) | 0 → 0 → 0 → 0 → 0 | Fail |
| [single-sec-financial-report-RI-001](final/single-sec-financial-report-RI-001/skills) | 0 → 0 → 0 → 0 → 0 | Fail |
| [single-sec-financial-report-RI-002](final/single-sec-financial-report-RI-002/skills) | 0 → 0 → 0 → 0 → 0 | Fail |
| [single-sec-financial-report-RI-003](final/single-sec-financial-report-RI-003/skills) | 0 → 0 → 0 → 0 → 0 | Fail |
| [single-fix-build-google-auto-all](final/single-fix-build-google-auto-all/skills) | 0 → 0 → 0 → 0 → 0 | Fail |
| [single-fix-build-google-auto-RI-001](final/single-fix-build-google-auto-RI-001/skills) | 0 → 0 → 0 → 0 → 0 | Fail |
| [single-fix-build-google-auto-RI-002](final/single-fix-build-google-auto-RI-002/skills) | 0 → 0 → 0 → 0 → 0 | Fail |

## Evidence and complete candidates

- [results-summary.json](results-summary.json) indexes every round, official
  score, projected test name/status, complete candidate, body-use evidence,
  original workspace inventory and usage. Repository evidence/candidate paths
  are relative; paths explicitly marked `local_only` refer to retained source
  material and are not GitHub downloads.
- `candidates/<input>/round-N/skills/` contains all files in each native
  candidate bundle, including supporting attachments. `final/<input>/skills/`
  is byte-identical to the selected last/first-full-score snapshot.
- `evidence/runs/<input>/round-N/` contains the exact native `result.json` and
  `RUN_RECORD.json`, unchanged score feedback, and `skill-tool-results.jsonl`.
  The latter is a projection of native Skill tool events, preserving original
  trajectory line numbers. It is not the complete execution trajectory.
- `evidence/repairs/<input>/round-N/repair.json` preserves the native repair
  outcome and existing native commit identifiers. Candidates were generated
  by SkillHone/DeepSeek Harness, not edited by the publication script.
- `artifacts/` contains primary files extracted directly from the original
  pre-verifier archives of the three passing executions: the PDDL plans and
  the two videos with their JSON reports. No missing outputs were rebuilt.
- Full original workspace archives (about 14.90 GB compressed), complete
  trajectories and native repair sessions remain in the local experiment
  archive. Those are not uploaded into this result directory.

## Interpretation and usage

- PDDL known-location and video RI-002 pass in round 1. Video RI-003 scores
  `0 → 0 → 0 → 1`, but its candidates are byte-identical across rounds 1–4:
  the first candidate passed on its fourth execution; there is no new round-4
  content change to credit for that pass.
- 69/101 execution rounds record zero Skill invocations. Of 32 rounds with
  positive invocation counts, 29 have exact full-body matches for at least
  one candidate `SKILL.md` in successful Skill tool results (YAML frontmatter
  excluded). All three passing executions have full-body evidence. Repairer
  reads of location hints are not counted as execution-side Skill use.
- Recorded native repair usage: 47,098,537 total tokens; 2,262 requests and
  2,108 responses in the repair audit. Recorded execution usage: 56,468,823
  total tokens, estimated cost **$27.3967463**. Discarded infrastructure
  attempts have a separate estimated **$2.88056195**, with eight unknown
  request counts. Repair cost and actual provider charges are unknown.
  In-flight requests without returned usage can be missing from token totals.
- Existing Gold qualification was reused. No new qualification matrix,
  baseline calls or score-based reruns were added for this upload.

## Runtime disclosure

[EXPERIMENT_CONFIG.json](EXPERIMENT_CONFIG.json) records the fixed protocol
and compatibility changes. This historical run used the frozen dataset
runner and a private BenchFlow **0.6.5** entry with pinned OpenHands SDK/tools
**1.28.1**, not the current repository `BenchmarkExecutor` API or current
BenchFlow 0.6.7 source. Results should not silently be treated as execution
under the current main-branch executor. Model, task, scoring and iteration
budgets were not changed by infrastructure recovery.

[COMPLETE.json](COMPLETE.json) records final counts. The discarded-attempt
ledger contains briefs only; abandoned output/trajectory/checkpoint packets
were deleted locally. Normal failures and normal budget-stop evidence remain.
No credentials or authorization headers are included.
