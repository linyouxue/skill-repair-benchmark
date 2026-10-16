# SkillGrad MAIN31 combined finalized publication

This directory contains the effective SkillGrad MAIN31 finalized publication after combining trusted LOCAL and accepted SERVER results.

- Method: SkillGrad
- Effective submission task count: 27
- LOCAL finalized tasks: 25
- SERVER finalized tasks: 2
- LOCAL verifier outcomes: PASS = 8, FAIL = 17
- SERVER additions preserved: lab-unit-harmonization, dynamic-object-aware-egomotion
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

## Canonical syzkaller S2 addition (2026-10-16)

Effective task count: 28 (LOCAL25 + SERVER3). The original 27 task directories and submission entries are preserved. `syzkaller-ppdev-syzlang` is finalized PASS at S2 under protocol v2 and `vllm/gpt-5.2`. Its raw S0 and S2 ACP/LLM trajectories, training rows, scoring metadata and exact repaired Skill are included; verifier implementation and private configuration are excluded. No model or formal execution was rerun. Azure BGP, energy-market and Druid remain excluded.
