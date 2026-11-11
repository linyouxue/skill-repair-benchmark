# WML / Claude Opus 4.7 controlled skill-repair experiments

- Method: Workflow-Localized Mechanism Learning (WML), with its original diagnosis and iterative repair mechanism.
- Controlled dataset: `skill-repair-controlled-datasets-20261020` (8 base tasks; 22 repair experiments and 33 control experiments).
- Repair model: `Claude-Opus-4.7` through Paratera (`https://llmapi.paratera.com/v1`).
- Executor: BenchFlow 0.6.7, `openhands`, model `paratera/Claude-Opus-4.7`, base URL `https://llmapi.paratera.com`.
- Final rerun: 2026-11-10 to 2026-11-11 after adding collision-safe task identities and mandatory persistent Skill preload audits.
- Human involvement: experiment operation, infrastructure-only retry/remediation, packaging, and an AI-assisted manual semantic review. Candidate Skill content was not manually rewritten after WML output.

## Final results

| Scope | Valid | Pass | Fail | Invalid |
|---|---:|---:|---:|---:|
| WML repairs | 22 | 12 | 10 | 0 |
| Controls | 33 | 21 | 12 | 0 |
| Total | 55 | 33 | 22 | 0 |

All 55 selected attempts have a valid `EXECUTION_AUDIT.json`, complete native result data, ACP and LLM trajectories, verifier output, a task-identity collision guard, and executor-level proof that the intended Skill bundle was preloaded. A task verifier failure remains a valid experimental result and is reported as `fail`; no infrastructure failure is counted as an experimental failure.

The manual semantic review reports 5/22 targets fully repaired and 17/22 not fully repaired under the Gold semantic criteria. For the 12 leave-one-out trials, all 12 retained the non-target Gold repairs. This semantic score is separate from the native task verifier score.

## Directory layout

- `manifest/`: authoritative 55-run manifest, repair/control summaries, remediation status, package index, and file checksums.
- `protocol/`: dataset catalog, repair-group definition, schema, and official scoring template.
- `method/`: the WML adapter and the exact evaluation/validation launchers used for this run.
- `repair/inputs/`: the 22 isolated repair inputs exposed to WML.
- `repair/candidates/`: all 22 complete WML output bundles, diagnoses, responses, and API-usage records.
- `review/`: the official-format semantic review CSV and detailed evidence notes.
- `experiments/repair/`: one final valid executor run for each of the 22 repaired candidates.
- `experiments/control/`: one final valid executor run for each of the 33 controls.

Within every experiment directory, `run/` contains the original executor metadata, result, verifier records, Skill snapshot, and trajectories. Large `.jsonl` files are stored losslessly as `.jsonl.gz`; `manifest/upload-package-index.json` records the mapping. Repeated staged task payloads are not duplicated. The task identity, patched Dockerfile, verifier, Skill snapshot, preflight hash, and audit remain present, while the fixed public task payload is identified by the dataset/provenance versions above.

Transient Debian/Ubuntu download failures and the legacy Google Auto CA bootstrap were handled only in per-attempt staging Dockerfiles. Task bodies, candidate Skill bundles, and verifiers were not modified during this remediation.
