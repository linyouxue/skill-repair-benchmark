# Evidence guide

`submission.json` is the evaluator-facing file. Each repaired Skill bundle is under `tasks/<task>/skills/`.

`summary.csv` and `run_status.json` contain the selected score, health classification, rounds, decisions, and source run for all 31 tasks.

`evidence_index.json` maps every selected task to its immutable raw method directory, repair loop, baseline, source task, terminal logs, and all valid or invalid rollout job directories. Those raw directories contain optimizer inputs and full replies, diagnosis samples, candidate Skill packages, gate results, executor trajectories, verifier stdout/results, and keep/revert reasons.

The experiment did not create an independent validation split or independent final-test split. Candidate acceptance and the reported score both use the same task gate. This limitation is recorded explicitly rather than inferred as held-out evaluation.

All 55 scored candidate gate results were executed as `ai360/openai/gpt-5.2`. Ten tasks reverted every candidate, so their final selected `method_result` is the imported original GPT-5.2 baseline and correctly retains its historical `openrouter/openai/gpt-5.2` provenance. This is selection provenance, not an optimizer/gate model substitution.

The v2 main run is retained unchanged. Only its four infrastructure-invalid task selections are replaced: Exoplanet, Bike, and Excel come from v3; SimPO comes from v4. All superseded and invalid attempts remain in their raw run directories.
