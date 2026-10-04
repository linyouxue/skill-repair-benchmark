# data-to-d3 - Clean SkillGrad Rerun

## Status

`FINALIZED PASS at S1`. This is the first completed MAIN clean-rerun canary. It is one task, not the aggregate 31-task result. The first repair succeeded and no S2 exists.

## Why this is a clean rerun

The historical formal outcomes are preserved, but their Diagnosis staging adapter did not faithfully expose the complete permitted ACP/result/output evidence. This chain restarts from authoritative original-skill S0 evidence after the adapter correction and inherits no historical Diagnosis, Momentum, Patch, or evolved Skill.

## Authoritative S0

- Task digest: `sha256:6bd955ce55b21352a441a5706b0e3faaad42b37891145e614b27387f44d38808`
- Original Skill SHA: `11645c768a9636beecd5ab0f440a788c7aae7e06605ce0ac6d4810299da4d115`
- Source ACP trajectory SHA: `0936b141631ecf2f643620662ecfdda6a3b19d679d095bfe3c6c663f98b776fd`
- Source/staged record counts: `19 / 19`
- S0 status: `valid_failure`

The raw source trajectory is `s0/source_acp_trajectory.jsonl`; `s0/trace.jsonl` is the complete method-visible staged representation.

## Method-visible evidence

Diagnosis could read the task prompt, current original Skill, complete staged ACP trace, Agent final output, 13 selected output-evidence records, the exact 55-file output inventory, and allowed generic execution/result metadata. The evidence gate, trajectory mapping, output evidence mapping, and output inventory equality all passed.

## Hidden evaluation information

Verifier failure explanation, failed test names and assertions, expected-vs-actual details, grader feedback, verifier stdout/stderr, Gold, reference repair, and hidden oracle material were not method-visible. The content audit found zero verifier-derived failure fields. Formal verdict files in `formal/` are archived evaluation evidence and were not Diagnosis inputs.

## Diagnosis

The clean Diagnosis result is `method/diagnosis_result.json` with SHA `8e19770cd2bf4d8db51c6f38d22c71a5538a9d87ec9a249b39637e0682c83822`. The readable diagnosis is `method/diagnosis.txt` with SHA `ccf66f07f29416e5bf15537b92d502bf95c8bb1691d4bf26ceacf50f4e07e18b`.

## Momentum and patch

Momentum transcript SHA is `d78e46b217b042da745137390c43118ef220c333208ed94539e670555d1df7fc`. The archived patch file SHA is `12689486f22a929045c591819dda21591b784bc75b478e670445d454b1b4dea1`; the source manifest's semantic patch digest `f6ae3c9d6041d280fe99ae65f825e5f07b1e73a1de562dc52c3e2cd5b8a66d72` is retained separately rather than substituted for the file hash.

## Frozen S1 Skill

The complete bundle is under `method/s1_skill/`. Its frozen identity is `sha256:bd49e68c070102e58b2da707f4f71e0214d60e40f961df188fc94bf47f60d795`; the exact runtime image is `sha256:c275b1f466da9625a1b92021c5b491e85f85a89ec392e7c44b20c8190ca2d24c`.

## Infrastructure recovery

Attempt `data-to-d3-clean-s1-formal-20261004-001` ended in a provider upstream timeout and was classified `infrastructure_invalid`, with no verifier verdict. It did not consume repair-failure budget and did not trigger Diagnosis, Momentum, Patcher, or S2. Recovery `data-to-d3-clean-s1-provider-upstream-timeout-20261004-001` authorized a same-round retry using the same task digest, frozen S1 bundle, image, model/reasoning, verifier, executor, and scoring semantics.

This is **1 repair round and 2 execution attempts**, not 2 repair rounds.

## Formal S1 result

Attempt `data-to-d3-clean-s1-formal-20261004-002` completed with `execution_ok=true`, `task_passed=true`, reward `1`, complete trajectory evidence, and verdict `valid_pass`. Its raw ACP trajectory is the source of truth. The task finalized at S1 and no S2 was created.

## Accounting semantics

S1 formal execution occurred. `FAILURE_ROUND_BUDGET_CONSUMED=false` means the infrastructure-invalid attempt did not advance the repair chain; it does not mean S1 was skipped. Clean accounting is `TOTAL_STARTED=1`, `FINALIZED=1`, `PASS=1`, `S5_FAIL=0` and remains separate from historical `27 / 8 / 19` accounting.

## Artifact provenance

1. Authoritative original-skill S0 was imported.
2. The source ACP trajectory was verified.
3. The repaired evidence adapter staged the complete trajectory.
4. Agent output, output inventory, and allowed result evidence were staged.
5. The content-level leak audit passed.
6. Clean Diagnosis was generated.
7. Momentum completed.
8. Patcher generated a new S1 Skill.
9. The S1 bundle was frozen and passed the provenance gate.
10. The exact runtime image was built and attested.
11. The first formal S1 attempt hit a provider upstream timeout.
12. That attempt was classified `infrastructure_invalid`.
13. No Diagnosis, Patch, or new repair round was triggered.
14. Same-round recovery was registered.
15. The exact same S1 task, bundle, and image were retried.
16. The retry returned `valid_pass`.
17. The task finalized PASS at S1.
18. No S2 was created.

## Integrity checks

The provenance directory records evidence gates, content audit, code hashes, bundle identity, image identity, launch manifests, and recovery identity. `runtime_attestation.json` is a valid-JSON normalization of a source file that had a trailing literal `\\n`; `runtime_attestation_source_metadata.json` binds both hashes and states the exact two-byte normalization. No historical result path is modified by this archive.
