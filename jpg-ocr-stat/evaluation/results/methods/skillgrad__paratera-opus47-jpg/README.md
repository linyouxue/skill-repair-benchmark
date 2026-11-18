# SkillGrad / Paratera Claude Opus 4.7 JPG generalization

The evaluated Skill is the unchanged final S1 bundle from [original-task PR #75](https://github.com/linyouxue/skill-repair-benchmark/pull/75), commit `75e03f0a14f050f63eeb050c6bd014ef1253be85`. Its SkillGrad SHA-256 is `6586b62d2a11e07d9b09713b16d23e8362094971608ece1c9861f0af1ba065ac`; the 18-file isolated executor bundle SHA-256 in every counted `executor_request.json` is `b9e0382cec772a87b44a1241aeac8f9606523817e060da29e5d3a3b221894392`. No Skill revision or selection followed these evaluations.

The evaluation source is commit `87e83a996d1fa33ea8380cb4a693ba077ef6574f`, manifest SHA-256 `1a84dc74460e3abb475a4d6ea980e75259aa9753c4de532b00363d4450b49b42`: current 20-receipt `group_01` and `group_03`, and unchanged 20-receipt `group_02`. The official `prepare_task.py` generated separate isolated tasks; the reference workbooks remained verifier-side. All counted attempts used the same OpenHands/BenchFlow route `paratera/Claude-Opus-4.7` and a 65-parent-iteration limit. Native request, configuration, usage and termination records are in the [downloadable original archives](evidence/README.md).

## Effective results

Each run is a fresh independent Agent execution. A valid Excel with a normal native score counts regardless of accuracy. When the native verifier crashed after a real Excel was exported, the unchanged Excel was scored once without a model using the frozen official `jpg-ocr-stat/verifier/score_accuracy.py` and that group's frozen oracle and 20-member spec. The `official_verifier_only_reassessment.json` reports are explicitly supplemental to, not replacements for, the retained failed native verifier records. Missing Excel, incomplete executor finalization and verifier dependency-install failure are excluded as anomalies. The first three effective attempts in actual start-time order are counted, with no score-based selection.

| Group | Run 01 | Run 02 | Run 03 | Mean | Original Skill baseline | Manual Round26 |
|---|---:|---:|---:|---:|---:|---:|
| group_01 | 27/40 native | 19/40 official reassessment | 18/40 native | 53.33% | 68.33% | 87.50% |
| group_02 | 37/40 native | 38/40 native | 38/40 native | 94.17% | 90.83% | 97.50% |
| group_03 | 31/40 native | 29/40 native | 24/40 official reassessment | 70.00% | 83.33% | 88.33% |

The original and manual baselines are published comparisons, not a strictly controlled head-to-head experiment: their model route, evaluation image version or executor configuration may differ. For the counted runs, group_01 dates were 45/60 and amounts 19/60; group_02 dates were 59/60 and amounts 54/60; group_03 dates were 42/60 and amounts 42/60. Group 01's amount extraction was the largest weakness; these observations did not alter the frozen Skill.

## Attempt chronology

The complete 23-attempt inventory with start times, source archive SHA-256, run IDs, original Excel SHA-256, scoring source and effective-run mapping is [`evidence/attempt_index.json`](evidence/attempt_index.json). The original archives are downloadable through the [Release asset index](evidence/README.md), which lists all 23 exact filenames, byte sizes, SHA-256 values and direct links. Their native ACP/LLM trajectories, generated files, executor configuration and available verifier output are retained inside the unchanged archives. The table below uses archive suffixes to make exclusions explicit. Effective results in each group are ordered by actual start time; the historical `Gx-Ry` stage label does not change that order.

| Group | Actual attempt order by start time | Treatment |
|---|---|---|
| 01 | `g1-r2-missing-excel-verifier-failure`, `g1-r3-native-675`, `g1-r1-verifier-failure-006`, `g1-r2-native-450-003`, `g1-r1-native-650-007` | First had no Excel; next three counted as 27, 19 and 18; last 26/40 native score retained, not selected. |
| 02 | `g2-r1-native-925-001`, `g2-r2-native-975-executor-finalize-error`, `g2-r3-verifier-infra-failure-no-result-json`, `g2-r3-native-950-002`, three installation failures (`002`-`004`), two reuse failures (`005`-`006`), `g2-r2-export-permission-failure-007`, `g2-r2-native-950-008` | The first three completed effective results are 37, 38 and 38, all native. The `r2-001` native 39/40 output is retained but its executor did not finalize or write `result.json`. The `r3-001` Excel scores 39/40 in an offline supplemental check, but verifier dependency installation failed on a GitHub connection reset before the native scorer ran. The `r2-007` container Excel was preserved separately after export permission failure and scores 38/40 offline, but the export and native verifier did not complete. These three are excluded as incomplete executions, with their original artifacts retained. Installation and reuse failures remain archived. |
| 03 | three installation failures (`001`-`003`), `g3-r1-native-775-004`, `g3-r2-native-000-005`, `g3-r3-native-725-006`, `g3-r2-verifier-failure-007` | Installation failures did not execute the model. `005` reached 65/65 with no Excel; its native 0/40 is retained but excluded as a missing-output anomaly. `004` and `006` count as 31 and 29; the real Excel from `007` was rescored by the official verifier as 24/40 after its native verifier crashed, and counts third. |

The group_01 19/40 and group_03 24/40 reassessments used the fixed official scorer on archived original Excel bytes after native verifier crashes. The group_02 `r2-007` 38/40 reassessment used the exact separately preserved container Excel copy; its SHA is recorded in the report, but the export failure remains an anomaly and the result is supplemental only. A separate group_02 `r3-001` offline 39/40 check is also supplemental because its native verifier failed during dependency installation before scoring began. No Opus call was made for reassessment; no run was retried because of a low score. All original abnormal attempts remain available through the [Release asset index](evidence/README.md).

## Evidence layout

- `group_01/run_01` through `run_03`, likewise `group_02` and `group_03`, contain the original Excel bytes, scoring record and an `attempt-reference.json` with the original run ID and archive path.
- [The evidence index](evidence/README.md) links every unchanged lossless native attempt archive hosted in the GitHub Release, including all failed or incomplete attempts and the later uncounted Group 01 run. The full ACP and LLM request/response trajectories, `executor_request.json`, `config.json`, `result.json` when generated, provider usage, and native verifier records are inside each archive. The `evidence/attempts/` paths in run references identify the original archive locations; the index resolves them to the downloadable assets. No LFS archive is required to read this Git submission.
- `evidence/reassessments/` contains the three no-model official scorer outputs. The scored Excel SHA and oracle SHA are recorded in each report. The fixed 40-field denominator is unchanged.

Provider usage is kept in the original run records. No verified Paratera unit price was available, so monetary cost remains `UNKNOWN`. The total assessment scope is all three groups, although `evaluation/results/methods/README.md` still describes only Group 02.
