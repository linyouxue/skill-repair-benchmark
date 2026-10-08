# SkillTTA GPT-5.2 — Gold31 Local30 execution evidence

This directory archives the 31 execution-valid tasks from the SkillTTA + repair-adapter GPT-5.2 run started on 2026-09-24. fix-druid-loophole-cve was completed on 2026-09-27 through the verified server/reverse-tunnel route and is included as a valid FAIL.

## Scope

- Method: SkillTTA + repair adapter (existing SKILL.md only)
- Method ID: skilltta-repair-gpt52-gold31-20260924
- Benchmark: manual-gold-defects-20260917-v25
- Model: openrouter/openai/gpt-5.2
- Valid tasks archived: 31
- Effective PASS: 5
- Effective FAIL: 26
- Druid: FAIL / valid execution

## Evidence policy

Each task's repaired_skill directory is copied from the final rollout's actual inputs/skills directory, not reconstructed from edit prose. Before publication, its adapter_result bundle hash is required to match the executor-observed skill bundle hash, and skill_context_preload_matches_expected must be true.

repaired_run/trajectory/acp_trajectory.jsonl is the raw ACP trajectory and source of truth. Core executor metadata and verifier text/JSON are retained. The five current guard3 replacements also include complete LLM trajectory, results.jsonl, training exports and authentic exported workspaces; obsolete local proxy credentials are redacted with source/published hashes recorded. Older unchanged task archives retain their original compact evidence layout. Dependency caches are excluded.

## Verifier adjudication

Raw executor outcomes are never overwritten. verifier-adjudications.json records verifier/runtime investigations separately. A raw FAIL is promoted only if the same frozen candidate passes a faithful repaired verifier. For fix-build-agentops, repairing the known tox/verifier drift still left the SkillTTA candidate failing while the Gold control passed in the same replay environment, so its effective outcome remains FAIL.

## Layout

    SkillTTA-GPT52-Gold31-Local30-20260924/
    ├── README.md
    ├── MANIFEST.json
    ├── STATUS.csv
    ├── submission.json
    ├── protocol.json
    ├── verifier-adjudications.json
    └── tasks/<task-id>/
        ├── original_run/
        │   └── trajectory/acp_trajectory.jsonl
        ├── repaired_skill/
        ├── repaired_run/
        │   ├── executor_request.json
        │   ├── result.json
        │   ├── benchmark_result.json
        │   ├── trajectory/acp_trajectory.jsonl
        │   └── verifier/...
        ├── method_output/
        └── task_state.json

Readable Markdown trajectory timelines are generated with the repository's canonical evaluation/results/export_trajectory.py and paired in trajectory_timelines/trajectory_timeline_index.json.

## Readable trajectory timelines

This archive now follows the repository method-result format with both original_run (before) and repaired_run (after) evidence for all 31 tasks. The repository's canonical evaluation/results/export_trajectory.py logic was used to generate deterministic readable Markdown timelines: 31 under trajectory_timelines/before, 31 under trajectory_timelines/after, and 0 unknown. trajectory_timelines/trajectory_timeline_index.json records the pairing metadata. Raw ACP JSONL remains the source of truth.

## 2026-10-08 completion guard3 replacements

[Replacement report and protocol disclosure](reruns/completion-guard3-20261008/README.md) · [Current replacement index](reruns/completion-guard3-20261008/replacement-index.json).

The listed canonical repaired runs and submission IDs now select the audited guard3 reruns. SkillTTA replaces Azure, Energy, Reserves and Python→Scala; MMG2Skill replaces Dialogue only. Each method directory contains only its corresponding replacements. Energy changes from FAIL to PASS; the other four remain valid FAILs. SkillTTA is now 5 PASS / 26 FAIL (31 valid tasks); MMG2Skill remains 5 PASS / 26 FAIL (31 valid tasks). All other task candidates, method diagnoses, baselines and historical semantic scores are unchanged. The full method bundles are byte-identical reused inputs; only these selected executions use guard3 with the same 60-step parent budget. No semantic judge was invoked for this publication, and execution PASS is not substituted for semantic TP. Prior canonical files remain available in Git history; MMG raw historical runs also remain under runs/.

Current readable export: 31 before / 31 after / 0 unknown unique rollouts. MMG includes explicitly historical runs in this count; current selection is defined by submission.json and task-index.json. RESULT_PROVENANCE.json identifies the original private snapshot SHA and public credential-sanitized derivative SHA; only the obsolete local proxy token is redacted, not workspace output content.

## 2026-10-08 additional guard3 replacement

[organize-messy-files: audited canonical rerun](reruns/completion-guard3-two-20261008/README.md) · [Replacement index](reruns/completion-guard3-two-20261008/replacement-index.json).

Organize had no textualized tool call. One ordinary progress announcement continued into real terminal work; real finish occurred at LLM13. All 103 fixed input files are byte-identical and sorted once. Two package document templates outside subject folders are an audit observation, not confirmed hidden-checker causality. The task remains a valid FAIL (4/6); overall counts remain 5 PASS / 26 FAIL. Full frozen method bundle and historical semantic scores remain unchanged. The previous canonical execution is retained in Git history.

Restored 20 supporting bundle files missing from the previous Git snapshot directly from the authentic rollout inputs; no existing bundle file was modified. The full 136-file bundle matches the frozen source SHA256 map. See [bundle reconciliation](reruns/completion-guard3-two-20261008/bundle-reconciliation.json).

The authentic large snapshot is hosted as a Release asset; `python restore_files.py --download-assets` restores the standard task path and checks size/SHA. See [large-files.json](large-files.json).
