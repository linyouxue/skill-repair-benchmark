# GPT-5.2 SkillGrad Clean Rerun (2026-10-04)

This directory contains the clean MAIN SkillGrad rerun started after the Diagnosis evidence adapter was corrected. It has independent accounting and currently contains one finalized task, `data-to-d3`; it is not the aggregate 31-task result.

## Historical vs clean results

Historical SkillGrad results remain under `evaluation/results/SkillGrad/` and are not overwritten. Their formal execution outcomes remain records of the bundles that were actually executed. A later audit found that the historical MAIN Diagnosis adapter did not faithfully stage the ACP trajectory and allowed result/output evidence, so those historical method chains are retained for audit and history but are not counted as clean-rerun results.

The clean rerun starts from authoritative original-skill S0 evidence, applies a fail-closed evidence boundary before Diagnosis, and does not inherit historical Diagnosis, Momentum, Patch, or evolved Skill artifacts. Historical accounting remains `FINALIZED=27`, `PASS=8`, `S5_FAIL=19`; clean accounting is recorded separately in `accounting.json`.

## Evidence boundary

Method-visible evidence is limited to the task prompt, current Skill, complete ACP trajectory, Agent-produced output evidence, output inventory, allowed execution/result metadata, and protocol-allowed reward/status. Verifier failure explanations, failed test names and assertions, expected-vs-actual details, grader feedback, verifier stdout/stderr, Gold, reference repairs, and hidden oracle material are excluded from Diagnosis.

Formal verifier verdict artifacts can appear in the archived evaluation result, but they were not visible to Diagnosis. The content-level audit reports `VERIFIER_DERIVED_FAILURE_FIELDS_FOUND=0`.

## Contents

- `run_manifest.json`: machine-readable identity and final status.
- `accounting.json`: clean and historical accounting separation.
- `artifact_inventory.sha256`: SHA256 inventory for every other file in this snapshot.
- `tasks/data-to-d3/`: authoritative S0, clean method chain, frozen S1, formal attempts, recovery evidence, and final result.
