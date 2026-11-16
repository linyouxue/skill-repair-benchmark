# Evidence guide

`submission.json` is the evaluator-facing file. Each repaired Skill bundle is under `tasks/<task>/skills/`.

`summary.csv` and `run_status.json` contain the selected score, health classification, rounds, decisions, and source run for all 15 tasks.

`evidence_index.json` maps every selected task to its immutable raw method directory, repair loop, baseline, source task, terminal logs, and all valid or invalid rollout job directories. Those raw directories contain optimizer inputs and full replies, diagnosis samples, candidate Skill packages, gate results, executor trajectories, verifier stdout/results, and keep/revert reasons.

The experiment did not create an independent validation split or independent final-test split. Tasks listed in `final_result_run_overrides` use a separate execution of the frozen selected Skill for the reported score, but it still uses the same task inputs and is not held out. This limitation is recorded explicitly rather than inferred as held-out evaluation.

This composite changes only jpg-ocr-stat. The other 14 task bundles, results, trajectories, and selections are inherited from the 2026-10-08 Gold15 run and are verified byte-identical to the earlier aggregate.
The superseded Gold15 aggregate and all JPG attempts are retained. Infrastructure-invalid or interrupted runs are evidence only and are not scored.
The refreshed JPG score is continuous field accuracy over 44 date/amount fields. Its task_passed flag is true only at reward 1.0, so aggregate interpretation should use the per-task reward as well as pass/fail.
No public three-group JPG generalization set was used for diagnosis, repair, candidate selection, or this composite score.
