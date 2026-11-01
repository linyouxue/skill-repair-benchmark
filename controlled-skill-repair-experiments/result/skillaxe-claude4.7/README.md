# SkillAxe / Claude 4.7

This directory contains the completed controlled Skill repair experiment for
`skill-repair-controlled-datasets-20261020`.

- Repair model: `Claude-Opus-4.7` through the Paratera OpenAI-compatible
  endpoint.
- Execution model: `vllm/Claude-Opus-4.7` with OpenHands.
- Harness: BenchFlow `0.6.5`.
- Required sequence: `export -> repair -> prepare-eval -> eval -> collect`.
- Scope: 22 repair trials and 33 controls.
- Completion: 22/22 repairs and 33/33 controls have one healthy, non-partial,
  verifier-scored result with `bench_exit_code == 0`.
- Result policy: ordinary semantic failures and healthy `reward=0` results are
  retained as measured; no score-based reruns were performed.
- Repository upload does not contain API keys or authorization headers.

The package collector output is [`results-summary.json`](./results-summary.json).
[`COMPLETE.json`](./COMPLETE.json) records the final 22/33 counts, and
[`EXPERIMENT_CONFIG.json`](./EXPERIMENT_CONFIG.json) records the fixed model,
endpoint, harness version, compatibility adjustments, and method disclosure.

## Aggregate results

| Slice | Runs | Mean reward | Pass | Fail |
|---|---:|---:|---:|---:|
| Repairs | 22 | 0.401500 | 8 | 14 |
| Controls | 33 | 0.565636 | 17 | 16 |
| Overall | 55 | 0.499982 | 25 | 30 |

## Evidence

`evidence/runs/` contains the selected `RUN_RECORD.json` and unique scored
`result.json` pair for every repair and control. The 110 files are indexed
with byte counts and SHA-256 hashes in
[`evidence/SELECTED_EVIDENCE_MANIFEST.json`](./evidence/SELECTED_EVIDENCE_MANIFEST.json).
The selected paths exactly match the 55 references emitted by the package
collector.

Historical attempts and iCloud recovery archives are intentionally not copied
into this repository result folder. They remain preserved in the local
experiment archive; this upload contains the complete minimal authoritative
evidence needed to audit every selected result.
