# Human-annotated Claude Gold15 repair evidence

人工标注的 Claude Opus 4.7 Gold15：15 个任务的最终修复 Skill bundle、selected validation trajectory 与 Gold 标注。

This directory is a manually curated Claude Gold reference set, not an automated Skill-repair method result.

- Model: openrouter/anthropic/claude-opus-4.7
- Tasks: 15
- Validation: 12 fresh-pass + 3 verifier-only-pass
- Gold registry version: claude-opus47-manual-gold-20261002-v15
- Source campaign: SkillGen-benchmarking/manual_annotation_runs_claude

## Layout

~~~text
HumanAnnotated-Claude-Gold15-20261002/
├── README.md
├── MANIFEST.json
├── STATUS.csv
├── gold.json
├── gold_repairs.json
├── submission.json
├── tasks/
│   └── <task-id>/
│       ├── repaired_skill/
│       └── repaired_run/
│           ├── executor_request.json
│           ├── benchmark_result.json
│           ├── result.json
│           ├── trajectory/acp_trajectory.jsonl
│           └── validation_evidence/
└── trajectory_timelines/
    ├── after/
    └── trajectory_timeline_index.json
~~~

As in HumanAnnotated-Gold31-20260917, token-heavy results.jsonl, workspace archives, model caches, and large verifier binaries are intentionally excluded. The raw acp_trajectory.jsonl remains the execution source of truth; readable timelines are deterministic exports using the repository evaluation/results/export_trajectory.py logic.

## Validation classes

The three verifier-only entries are:
- fix-build-agentops
- reserves-at-risk-calc
- azure-bgp-oscillation-route-leak

Their raw Agent run metadata is preserved unchanged. Separate replay/contract evidence is archived under repaired_run/validation_evidence/; verifier-only validation is never rewritten into the raw benchmark_result.json.

## Repaired Skill provenance

For 13 tasks, the published candidate bundle is byte-identical to the currently readable selected run inputs/skills. For manufacturing-equipment-maintenance and dynamic-object-aware-egomotion, current Windows junction traversal does not expose every frozen input file, but each selected run result.json records the exact bundle file count/bytes/hash and confirms the full candidate bundle was preloaded with skill_context_preload_matches_expected=true; the published bundle matches those recorded counts and bytes.

## Important scope note

This Gold includes validated Skill repairs and instruction-adherence/quality reinforcements as recorded in gold_repairs.json. A PASS establishes the recorded validation contract, not that every added sentence is independently minimal or that every broader semantic/tool-contract limitation is solved. Those limitations are retained in the Gold metadata.
