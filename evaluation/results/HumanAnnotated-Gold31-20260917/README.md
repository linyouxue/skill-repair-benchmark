# Human-annotated Gold31 repair evidence

**This directory is the manually annotated / human-curated Gold repair reference set. It is not an automated Skill-repair method result.**

It archives the final repaired Skill text and the validation trajectory selected during the manual annotation campaign for the 31 Gold tasks (57 Gold defects). The final Gold annotation snapshot is dated 2026-09-17; this repository package was prepared for publication on 2026-09-24.

## Scope and validation classes

- **27 fresh-pass** tasks: the selected repaired rollout completed normally with the official verifier and `task_passed=true` / full reward.
- **3 verifier-only-pass** tasks: the original Agent trajectory and repaired Skill are preserved, while the final pass was established by a faithful official-verifier replay or final-artifact completion without additional model calls. These are `exoplanet-detection-period`, `fix-build-agentops`, and `jpg-ocr-stat`; they must not be reported as ordinary fresh comparable PASS runs.
- **1 content-validated-task-spec-blocked** task: `enterprise-information-search`. The repaired rollout was execution-valid and its three substantive answer values passed the official content test, but the task example represented token counts as strings while the verifier required JSON numbers; raw reward remained 0. It is retained in Gold because the Skill repair's content behavior was directly validated, not because the task obtained reward 1.

## Per-task layout

```text
HumanAnnotated-Gold31-20260917/
├── README.md
├── MANIFEST.json
├── STATUS.csv
├── gold.json
├── gold_repairs.json
├── submission.json
└── tasks/
    └── <task-id>/
        ├── repaired_skill/
        │   └── <skill-name>/SKILL.md
        └── repaired_run/
            ├── executor_request.json
            ├── benchmark_result.json
            ├── result.json
            ├── trajectory/acp_trajectory.jsonl
            └── validation_evidence/   # only when a replay/special validation is needed

trajectory_timelines/
├── after/
│   └── <task-id>__manual-annotation__<run-id>.md
└── trajectory_timeline_index.json
```

`repaired_skill/` is the complete frozen `inputs/skills` bundle used by the selected validation trajectory, including unchanged companion Skills and supporting files; it is copied from the selected run rather than reconstructed from prose repair notes. `acp_trajectory.jsonl` is the raw ACP execution trajectory and source of truth. `executor_request.json`, `result.json`, and `benchmark_result.json` preserve the run contract and outcome. Token-heavy duplicate `results.jsonl`, workspace tarballs, and cache files are intentionally excluded.

The repository's canonical `evaluation/results/export_trajectory.py` recognizes all 31 archived ACP trajectories as `method-skill` / `after`. The readable `trajectory_timelines/` export is generated from those raw trajectories without changing the source evidence.

## Special validation provenance

- **exoplanet-detection-period**: Round-1 r006 generated `period.txt=5.35892`; WSL/Docker bridge instability interrupted automatic verifier finalization. The exact recovered 8-byte output was checked with the unchanged official verifier in the original container: 4/4 tests, reward 1, zero model calls during replay. The raw rollout remains non-comparable and is not rewritten.
- **fix-build-agentops**: Round-2 r003 used the repaired bundle and completed the Agent trajectory. The raw verifier drifted to a newer tox where absent py37/38/39 environments were counted as failures; a faithful verifier-only replay pinned the historical CI version `tox==4.15.0`, reapplied the unchanged saved patch, and passed 3/3. The original raw reward is preserved.
- **jpg-ocr-stat**: the final minimal repair keeps OCR-pass provenance and field-local adjudication. The final checkpoint was completed with the already resolved targeted OCR values and the unchanged official `test_outputs.py::test_outputs()` passed strict 22-row equality. This is labeled verifier-only/final-artifact validation, not a fresh task-pass rollout.
- **enterprise-information-search**: substantive answers were correct; only the independent token-field type contract conflict prevented full reward.

## Source of truth

`MANIFEST.json` records the selected run and validation class for every task. `gold.json` and `gold_repairs.json` are the final human-curated defect/repair metadata snapshots used to define Gold31. Per-task trajectories and repaired Skill text are the direct execution evidence.

