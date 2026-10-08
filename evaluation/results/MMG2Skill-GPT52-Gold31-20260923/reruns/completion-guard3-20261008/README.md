# Completion guard3 replacements — 2026-10-08

The user authorized fresh reruns of these previously failed tasks with completion guard 3. The listed runs now replace their prior canonical `tasks/<task_id>/repaired_run` selections. This is a mixed-protocol execution snapshot, not a claim that every task was run with guard3.

| Task | Prior result | Current result | Current rollout |
|---|---|---|---|
| dialogue-parser | FAIL | FAIL | `dialogue-parser-mmg2skill-gpt52-guard3-20261008-r002` |

All current runs have valid original verifier outcomes, complete ACP and LLM trajectories, training rows, authentic exported workspaces and full frozen method inputs. Valid FAILs are retained. Prior canonical runs remain in Git history at commit `a6109102a9172559a4cb2d2957c16b1cc01c70a0` and private source batches.

Protocol: `openrouter/openai/gpt-5.2`, explicit reasoning omitted, output ceiling 32768, guard continuation limit 3, one shared 60-iteration parent budget. Method generation/bundles and original baselines were reused. No new method, retrieval, embedding or judge calls; no remaining infrastructure fault. Independent fresh randomness means the result change does not isolate the causal effect of guard3.

Raw generic `executor_request.protocol` still states default guard 1; actual config/result/ACP prove guard 3. Saved SDK reasoning_effort defaults to high while captured provider fields omit explicit reasoning; omission is not proof of none. Provider callbacks log total_tokens only; training input/output splits are placeholders. All selected runs have n_skill_invocations=0 and full Skill body preload exposure. Python→Scala inherits reconstructed input/custom verifier limitations. Reserves retains historical cache proof fields; its new build verification and authentic run are authoritative.

The public snapshots redact only the obsolete local BenchFlow proxy credential from agent_settings.json. RESULT_PROVENANCE.json records source/public file and member hashes; real workspace content is retained, never reconstructed. Raw source snapshots remain private and immutable. Other run files are byte-identical, except any explicitly listed credential redaction.

The first attempt failed before model execution due to Docker network pool/build connectivity. Reserves reused cached Ubuntu packages after a pre-model APT proxy interruption; targeted offline input/pin/output checks passed. Recovery evidence and scripts are under recovery/. The 30-minute monitor was deleted after audit. Do not execute archived launch scripts blindly.

Semantic Gold scores are not recomputed or inferred from execution PASS. Existing diagnoses and any historical scoring are retained.

Rebuild readable timelines without duplicate copies: `python reruns/completion-guard3-20261008/recovery/export_unique_timelines.py --root .` (add `--dry-run` to preview). This wrapper uses the repository exporter without constructing or editing index rows.
