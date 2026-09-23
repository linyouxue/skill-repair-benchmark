# CausalFlow → Skill / Claude Opus 4.7 / Gold 15

Completed 2026-09-23: **3 PASS, 12 FAIL, 0 INFRA_ERROR under the explicitly revised AgentOps verifier matrix**, covering 15 tasks and 32 Gold defects. Verified execution pass rate is **20%**.

This is a CausalFlow-to-Skill adaptation: action-level counterfactual analysis and repair are followed by one Skill adaptation and a fresh task rollout. Action replay success and fresh Skill execution success are different measurements.

**All 15 final Skill bundles are byte-identical to their original bundles.** The method submitted no diagnoses or Skill edits. Fresh passes therefore do not demonstrate a Skill-content repair effect.

## Results

- [Final report and complete metric table](final-review-supported-matrix/FINAL-REPORT.md)
- [Machine-readable metrics and per-task outcomes](final-review-supported-matrix/final-metrics.json), [CSV](final-review-supported-matrix/complete-metrics.csv)
- [Selected task/run/bundle index](task-index.json) and [portable executor registry](executor-results.json)
- [Before/after trajectory timelines](trajectory_timelines/trajectory_timeline_index.json): 15 reused original runs and 15 selected fresh runs.
- [Submission](submission.json), with complete bundles under `submission/tasks/<task_id>/skills/`
- [Original-protocol report](final-review/FINAL-REPORT.md): 3 PASS, 11 FAIL, 1 INFRA_ERROR; retained separately rather than relabeling the original execution.

| Scoring | Diagnosis TP / FP / FN | Repair TP / FP / FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| Original Gold content judgment | 0 / 0 / 32 | 0 / 0 / 32 | N/A | 0% | 0% |
| Requested valid F→P override | 5 / 0 / 27 | 5 / 0 / 27 | 100% | 15.625% | 27.027% |

The override assigns every Gold defect in a valid F→P task to TP and sets that task's FP/FN to zero. It is an execution-conditioned scoring convention, not a replacement of the independent content judgments. Location retains the original hit count divided by the new TP: 0/5. Original Gold responses, confidence, review and regression judgments are preserved. No new model or judge requests were made for this publication.

## Evidence and exceptions

- `runs/` preserves real trajectories, rollout rows, verifier output and exported artifacts. Use `task-index.json` to select the 15 current runs; other run IDs are historical infrastructure/recovery evidence, not extra trials or valid model failures.
- `causalflow/` and `generation/` preserve method audits, counterfactual results and adapter outputs. There were 344 interventions, two causal steps, six repair candidates and two successful action repairs. Only two tasks required a Skill adaptation model call; neither changed a Skill.
- `gold-evaluation/` contains the original GPT-5.5 medium responses. `final-review-supported-matrix/gold-v1.4/` contains offline scoring with the selected execution results.
- `fix-build-agentops`: the original py37–py312 verifier matrix conflicts with its pinned LangChain dependencies, which require Python ≥3.8.1. The disclosed revision runs the original tests on py38–py312 against the real exported model patch. All five environments complete, yielding a valid FAIL. This was verifier-only recovery; the original six-environment protocol remains isolated as INFRA_ERROR. See [recovery audit](verifier-recovery-agentops-supported-matrix-20260923/final-audit.json).
- `flink-query`: r001 had a root Maven-cache infrastructure failure and no recoverable workspace. r002 is the authorized fresh-only replacement using the same frozen Skill. Its real pre-verifier workspace archive and three passing tests are retained. See [r002 audit](final-audit-flink-r002.json).
- `python-scala-translation`: its historical input used an explicitly authorized reconstruction of erroneously redacted code. `reconstructed-inputs/` retains the provenance; this is not described as a lossless original trajectory.
- `shock-analysis-supply`: the task's Playwright/Excel-only requirements are not fully matched by the basic tool harness. A completed verifier does not remove that environmental limitation.
- Original-skill runs are reused from [the published Opus 4.7 baseline](../Opus47-OriginalSkill-79Tasks-20260920/README.md); per-task paths are in `task-index.json`. No original-skill run was repeated.
- Native `n_skill_invocations` totals 1; all 15 tasks have independently audited full-Skill-body exposure. Invocation count and injected content exposure are reported separately.

## Configuration and reproduction

Method, adapter and fresh execution use `anthropic/claude-opus-4.7`, with 32768 output tokens and no explicit temperature, reasoning-effort or thinking setting. Fresh iteration limits are 65 for JPG and 60 for other tasks. Gold uses GPT-5.5 medium, 8192 output tokens, temperature omitted, prompt v2.1 and scorer v1.4.

Recompute from the retained judgments without API calls, from the repository root:

```sh
python evaluation/results/CausalFlow-Skill-Opus47-Gold15-20260922/build_final_report.py --supported-matrix
```

Omit `--supported-matrix` to reproduce the original-protocol report with AgentOps quarantined. Earlier generated reports are retained on recomputation. The original local reporting script is archived in `history/`; the published version resolves local paths and the repository scorer portably. Raw evidence keeps historical paths unchanged. Dependencies required by the scorer are declared in the repository.

[PACKAGING.json](PACKAGING.json) records packaging scope; [PUBLICATION_VALIDATION.json](PUBLICATION_VALIDATION.json) records the selected-run artifact check and publication checks. Dependency binaries and local runtime caches are excluded; selected trajectories and workspace archives are not truncated.
