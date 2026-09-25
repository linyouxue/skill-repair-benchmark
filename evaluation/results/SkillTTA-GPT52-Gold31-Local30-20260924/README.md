# SkillTTA GPT-5.2 — Gold31 Local30 execution evidence

This directory archives the 30 execution-valid local tasks from the SkillTTA + repair-adapter GPT-5.2 run started on 2026-09-24. fix-druid-loophole-cve is intentionally excluded because provider-region access prevented a valid local rollout.

## Scope

- Method: SkillTTA + repair adapter (existing SKILL.md only)
- Method ID: skilltta-repair-gpt52-gold31-20260924
- Benchmark: manual-gold-defects-20260917-v25
- Model: openrouter/openai/gpt-5.2
- Valid tasks archived: 30
- Effective PASS: 4
- Effective FAIL: 26
- Druid: NOT_RUN / excluded from Local30

## Evidence policy

Each task's repaired_skill directory is copied from the final rollout's actual inputs/skills directory, not reconstructed from edit prose. Before publication, its adapter_result bundle hash is required to match the executor-observed skill bundle hash, and skill_context_preload_matches_expected must be true.

repaired_run/trajectory/acp_trajectory.jsonl is the raw ACP trajectory and source of truth. Core executor metadata and verifier text/JSON are retained. Token-heavy duplicate results.jsonl, trainer mirrors, workspace tarballs, caches, and raw provider request/response dumps are intentionally excluded.

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

Readable Markdown trajectory timelines can be generated later with the repository's canonical evaluation/results/export_trajectory.py; the raw ACP JSONL files in this archive are already complete source evidence.

## Readable trajectory timelines

This archive now follows the repository method-result format with both original_run (before) and repaired_run (after) evidence for all 30 tasks. The repository's canonical evaluation/results/export_trajectory.py logic was used to generate deterministic readable Markdown timelines: 30 under trajectory_timelines/before, 30 under trajectory_timelines/after, and 0 unknown. trajectory_timeline_index.json records the pairing metadata. Raw ACP JSONL remains the source of truth.
