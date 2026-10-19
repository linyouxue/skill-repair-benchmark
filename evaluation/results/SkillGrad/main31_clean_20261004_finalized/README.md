# SkillGrad MAIN31 combined finalized publication

This directory contains the effective SkillGrad MAIN31 finalized publication after preserving the 25 trusted LOCAL results.

- Method: SkillGrad
- Effective submission task count: 25
- LOCAL finalized tasks: 25
- SERVER finalized tasks: 0
- LOCAL verifier outcomes: PASS = 8, FAIL = 17
- Superseded SERVER additions removed; canonical replacements are in `../main31_local_recovery_four_20261019_v1/`.
- Ownership conflict retained but excluded: paper-anonymizer-server-ownership-conflict.json
- fix-druid-loophole-cve is not included; it is server-owned and has no finalized result in this publication.

The eight tasks added by this publication gate are:

- reserves-at-risk-calc: FAIL @ S5
- software-dependency-audit: PASS @ S2
- bike-rebalance: FAIL @ S5
- video-silence-remover: FAIL @ S5
- fix-build-agentops: FAIL @ S5
- fix-build-google-auto: FAIL @ S5
- multilingual-video-dubbing: PASS @ S1
- seismic-phase-picking: PASS @ S1

Each effective task directory contains:

```text
tasks/<task>/
|-- repaired_skill/
|-- original_run/
`-- repaired_run/
```

Only publication-allowlisted run evidence is included: `executor_request.json`,
`result.json`, `benchmark_result.json`, and `trajectory/acp_trajectory.jsonl`.
Verifier, Gold, oracle, private evaluator, secret, discarded, debug, timeout, and
polluted historical-chain artifacts are excluded. The effective task set is
defined by `submission.json` and the generated trajectory timeline index.
