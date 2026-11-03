# SkillHone / GPT-5.2 xhigh - unified executor

Completed campaign `controlled-skillhone-unified-20261102` on
`skill-repair-controlled-datasets-20261020`. This replaces the previous results
at this path; no old score, candidate or interrupted run was reused.

**22 independent inputs, 79 valid rounds, 10 full-score stops, 12 five-round
stops (45.45% final full-score rate).** Ordinary failures and zero scores count.

Repair and execution both use Tatu GPT-5.2/xhigh, maximum output 16384 per
request. Each round performs one native SkillHone/DSH repair and one original
task execution through the shared `BenchmarkExecutor` in `method-skill` mode.
Repair keeps the original 1200-second budget. The full candidate bundle is
passed to the executor. Each Step has at most 60 root Agent iterations; one
text-only continuation shares that budget. Three workers refill rolling slots,
including native resumptions. Existing Gold qualification is reused. No new
controls, model calls or verifier calls were added for publication.

## Results

| Condition | Inputs | Full-score stops | Valid rounds |
|---|---:|---:|---:|
| Known error location | 5 | 3 | 14 |
| Single-fault leave-one-out | 12 | 7 | 40 |
| All-fault condition | 5 | 0 | 25 |
| Total | 22 | 10 | 79 |

`single` in the source plan combines 12 leave-one-out and 5 all-fault inputs.
A pass is official reward 1. These task outcomes do not independently establish
semantic defect repair or causal improvement. The two groups have different tasks.

## Independent frozen-candidate rerun (guard3)

The completed **rerun** `controlled-skillhone-guard3-rerun21-20261103` executes
21 selected source-round candidates from 11 inputs once each, with **zero new
SkillHone/DSH repairs**. The candidates are unchanged. Text-only continuations
have a total limit of 3 and still share the 60-root-iteration budget.

| Rerun inputs | Independent execution slots | Full-score executions | Zero-score executions | New repairs |
|---:|---:|---:|---:|---:|
| 11 | 21 | 3 (14.29%) | 18 | 0 |

The rerun column below identifies each selected source round; a dash means
that input was not rerun. Original round rewards and final outcomes remain the
79-round primary results. Do not add the 3 rerun passes to the primary 10/22
rate. All three rerun passes used only 0 or 1 continuation, so these extra
single executions do not establish an effect of raising the guard limit.

See [the rerun report](rerun-guard3-21-20261103/RERUN_RESULTS.md) for all 21
slot scores, actual iterations/guard counts, products, usage and limitations.
Eight native API resumptions retain partial trajectories and are not training
ready; D3 browser-binary equivalence and four Flink slots' exact-body
observability remain limited. Google RI001 source R5 includes the authorized
sudo interruption and scoring-only recovery without a model rerun.

| Input | Original round rewards | Original final | Frozen-candidate rerun (source round: reward) |
|---|---|---|---|
| [location-dialogue-parser](final/location-dialogue-parser/skills) | 0.833 → 1 | Pass | — |
| [location-data-to-d3](final/location-data-to-d3/skills) | 0 → 0 → 0 → 0 → 0 | Fail | R3: 1, R4: 0 |
| [location-flink-query](final/location-flink-query/skills) | 0 → 0 → 0 → 0 → 0 | Fail | R2: 0, R3: 0, R4: 0 |
| [single-flink-query-all](final/single-flink-query-all/skills) | 0 → 0 → 0 → 0 → 0 | Fail | — |
| [single-flink-query-RI-001](final/single-flink-query-RI-001/skills) | 0 → 0 → 0 → 0 → 0 | Fail | R1: 0 |
| [single-flink-query-RI-002](final/single-flink-query-RI-002/skills) | 0 → 0 → 0 → 0 → 0 | Fail | — |
| [location-manufacturing-equipment-maintenance](final/location-manufacturing-equipment-maintenance/skills) | 1 | Pass | — |
| [single-manufacturing-equipment-maintenance-all](final/single-manufacturing-equipment-maintenance-all/skills) | 0 → 0 → 0 → 0 → 0 | Fail | — |
| [single-manufacturing-equipment-maintenance-RI-001](final/single-manufacturing-equipment-maintenance-RI-001/skills) | 1 | Pass | — |
| [single-manufacturing-equipment-maintenance-RI-002](final/single-manufacturing-equipment-maintenance-RI-002/skills) | 0 → 0 → 0 → 0 → 1 | Pass | R2: 0 |
| [location-pddl-airport-planning](final/location-pddl-airport-planning/skills) | 1 | Pass | — |
| [single-video-silence-remover-all](final/single-video-silence-remover-all/skills) | 0 → 0 → 0 → 0 → 0 | Fail | R1: 0, R5: 0 |
| [single-video-silence-remover-RI-001](final/single-video-silence-remover-RI-001/skills) | 0 → 1 | Pass | — |
| [single-video-silence-remover-RI-002](final/single-video-silence-remover-RI-002/skills) | 0 → 1 | Pass | — |
| [single-video-silence-remover-RI-003](final/single-video-silence-remover-RI-003/skills) | 1 | Pass | — |
| [single-sec-financial-report-all](final/single-sec-financial-report-all/skills) | 0 → 0 → 0 → 0 → 0 | Fail | — |
| [single-sec-financial-report-RI-001](final/single-sec-financial-report-RI-001/skills) | 0 → 1 | Pass | R1: 1 |
| [single-sec-financial-report-RI-002](final/single-sec-financial-report-RI-002/skills) | 0 → 0 → 0 → 0 → 0 | Fail | R1: 0, R2: 0 |
| [single-sec-financial-report-RI-003](final/single-sec-financial-report-RI-003/skills) | 0 → 0 → 0 → 0 → 0 | Fail | R4: 0 |
| [single-fix-build-google-auto-all](final/single-fix-build-google-auto-all/skills) | 0 → 0 → 0 → 0 → 0 | Fail | R1: 0, R3: 0, R4: 0 |
| [single-fix-build-google-auto-RI-001](final/single-fix-build-google-auto-RI-001/skills) | 0 → 0 → 0 → 0 → 0 | Fail | R2: 0, R3: 0, R4: 0, R5: 0 |
| [single-fix-build-google-auto-RI-002](final/single-fix-build-google-auto-RI-002/skills) | 0 → 1 | Pass | R1: 1 |

## Evidence and complete candidates

- [FINAL_RESULTS.md](FINAL_RESULTS.md) gives two-group per-round tables, audit
  findings, limitations, failure patterns and accounting in Chinese.
- [results-summary.json](results-summary.json) indexes all 79 selected scores,
  complete candidates, native repair outcomes, instruction projections, usage
  and actual workspace inventories. `local_only` entries are not downloads.
- `candidates/<input>/round-N/skills/` and `final/<input>/skills/` preserve all
  bytes, including supporting files and native bytecode in the evaluated bundle.
  They match frozen execution inputs and native commit trees.
- `evidence/runs/` includes exact canonical `result.json`,
  `benchmark_result.json`, `adapter-response.json`, timing, public prompts,
  test-status feedback, trajectory inventories and derived audits.
- `evidence/runs/.../preload/` projects actual provider-returned instructions
  without changing source redaction, preserving source line references. These
  files are not full execution trajectories or training rows.
- `evidence/repairs/` includes native outcomes and provenance/usage audits.
  Full native sessions remain local. The host did not author candidates.
- `artifacts/` contains primary deliverables from all ten successful executions,
  extracted directly from their original pre-verifier workspace archives. No
  missing products were reconstructed. Google `failed_reasons.txt` is the
  agent's required public diagnosis note, not a hidden verifier answer.
- All 79 real workspace archives remain local: 13,144,476,938 compressed bytes.
  The existing full-archive validation inventory is published. Full execution
  ACP/LLM trajectories, training rows and native repair sessions stay local.

## Interpretation and usage

- Every round has `n_skill_invocations=0`, with no actual `invoke_skill` calls.
  Skill evidence is full-body persistent context preload and provider
  instructions, not active invocation of a Skill tool.
- 59 rounds have raw-exact body matches in all successful responses. In 20
  Flink rounds, example passwords are redacted in logs; the repository redactor
  reproduces the differences exactly. Eight also retain intact native contexts;
  twelve lack that independent raw copy. This is an observability limit, not
  evidence of absent input.
- Twelve native-continuation rounds retain valid official scores and partial
  ACP / `training_ready=false`. Do not present them as complete ACP or SFT data.
  Publication does not rerun or fill their missing ACP events.
- Dialogue R2, video RI-002 R2 and SEC RI-001 R2 reuse the previous candidate.
  SEC RI-001 has no change in either round and equals the starting frozen
  bundle. These passes cannot be credited to a new round-2 repair.
- Execution: 2178 attempts, 2148 HTTP 200 and 30 HTTP 500; 94,651,450 recorded
  total tokens, 2162 root iterations. The canonical execution cost estimate is
  **$52.2658759**, not the actual bill or the whole experiment's price.
- Repair: 1778 dispatched attempts, 1721 HTTP 200 and 57 transport errors;
  1720 complete native usages total 38,865,525 tokens. One extra HTTP 200 was
  truncated by the outer budget and has unknown usage. Seventy-nine title
  helper intents were blocked before fetch and excluded from dispatched calls.
- Including the one 34-token connectivity probe, 3957 request attempts have
  133,517,009 known tokens. Usage for 88 requests, repair costs and actual
  supplier charges remain unknown; missing usage is never set to zero.
- No forbidden Gold/verifier/other-trial access or hidden test edits were
  observed. Historical syscall writer attestation and complete retired-container
  mount receipts are unavailable. Normal low scores and documented path/PDF
  friction remain measured outcomes. Google public integration-test POM changes
  are disclosed separately from assertions or skip-test settings.

## Runtime disclosure

[EXPERIMENT_CONFIG.json](EXPERIMENT_CONFIG.json) records the frozen protocol.
This campaign actually imports the existing shared `benchmark_executor`
source; it does not use the old private PyPI BenchFlow 0.6.5 entry or a copied
executor. CLI commit is `2df8a2835d3f1bd2f2eadf5a7a2e1ad0dfb0d271`, SDK/tools
are 1.28.1. Runtime and free preflight receipts are retained.

Local dependency caches, credentials, raw failed packets and full workspace
archives are not uploaded. This directory replaces the old current result
tree without rewriting Git history. Other methods and repository rules stay unchanged.
