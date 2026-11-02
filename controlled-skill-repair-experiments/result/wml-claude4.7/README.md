# WML / Claude 4.7

Selected final results from the supplied `wml-claude4.7-controlled-results-final.zip`
for `skill-repair-controlled-datasets-20261020`. This publication reads the
provided records; it does not run the packaged scripts or repeat any experiment.

| Slice | Selected runs | Pass | Fail |
|---|---:|---:|---:|
| WML repairs | 22 | 12 | 10 |
| Controls | 33 | 19 | 14 |
| Total | 55 | 31 | 24 |

Repair model: `Claude-Opus-4.7`; execution: OpenHands with
`openai/Claude-Opus-4.7`, through the supplied Paratera endpoint configuration.
The 55 selected records have a scored result, no native error/partial flag,
and `bench_exit_code == 0`. These checks do not replace a new semantic or
complete trajectory audit. Budgets/seeds not frozen in the source are not
retroactively invented here.

## Contents

- [results-summary.json](results-summary.json): portable paths for the 55
  selected result/RUN_RECORD pairs and original source-member references.
- [COMPLETE.json](COMPLETE.json) and [EXPERIMENT_CONFIG.json](EXPERIMENT_CONFIG.json):
  final counts and supplied method/model identity.
- `evidence/runs/`: exact selected native `result.json` and `RUN_RECORD.json`.
  [Evidence index](evidence/SELECTED_EVIDENCE_INDEX.json) maps the source members.
- `candidates/`: all 22 complete supplied WML candidates and native repair/usage
  records. `inputs/`, `method/` and `protocol/` preserve the supplied small
  input bundles, method code and protocol metadata.
- `review/`: the source's 22-row semantic review and its evidence. The source
  labels this as AI-assisted review, not an independent human sign-off. Its
  strict target-repair count is 5/22 and non-target preservation is 12/12 for
  leave-one-out cases; these are separate from the 12 original-task passes.
- `source/`: unchanged supplied README, final summaries and historical
  collector outputs. Some historical collector rows are invalid, ambiguous
  or missing; only the explicit 55 entries in the final source manifest are
  selected for the table and evidence above.

Prepared task environments/assets, complete trajectories and old attempts are
retained in the original source ZIP rather than duplicated into Git. The source
README documents an earlier credential redaction in trajectory copies; those
full trajectories are not published here. No keys or authorization headers are
added. Existing repository READMEs and other methods are unchanged.

## Selected records

| Type | Experiment | Reward | Source status |
|---|---|---:|---|
| wml_repair | location-data-to-d3 | 0.0 | fail |
| wml_repair | location-dialogue-parser | 0.833 | fail |
| wml_repair | location-flink-query | 0.0 | fail |
| wml_repair | location-manufacturing-equipment-maintenance | 1.0 | pass |
| wml_repair | location-pddl-airport-planning | 0.0 | fail |
| wml_repair | single-fix-build-google-auto-RI-001 | 1.0 | pass |
| wml_repair | single-fix-build-google-auto-RI-002 | 1.0 | pass |
| wml_repair | single-fix-build-google-auto-all | 1.0 | pass |
| wml_repair | single-flink-query-RI-001 | 0.0 | fail |
| wml_repair | single-flink-query-RI-002 | 0.0 | fail |
| wml_repair | single-flink-query-all | 0.0 | fail |
| wml_repair | single-manufacturing-equipment-maintenance-RI-001 | 1.0 | pass |
| wml_repair | single-manufacturing-equipment-maintenance-RI-002 | 1.0 | pass |
| wml_repair | single-manufacturing-equipment-maintenance-all | 1.0 | pass |
| wml_repair | single-sec-financial-report-RI-001 | 1.0 | pass |
| wml_repair | single-sec-financial-report-RI-002 | 1.0 | pass |
| wml_repair | single-sec-financial-report-RI-003 | 0.0 | fail |
| wml_repair | single-sec-financial-report-all | 1.0 | pass |
| wml_repair | single-video-silence-remover-RI-001 | 0.0 | fail |
| wml_repair | single-video-silence-remover-RI-002 | 1.0 | pass |
| wml_repair | single-video-silence-remover-RI-003 | 0.0 | fail |
| wml_repair | single-video-silence-remover-all | 1.0 | pass |
| control | data-to-d3__full_gold | 1.0 | pass |
| control | data-to-d3__original | 0.0 | fail |
| control | dialogue-parser__full_gold | 0.833 | fail |
| control | dialogue-parser__original | 0.833 | fail |
| control | fix-build-google-auto__all_faults | 1.0 | pass |
| control | fix-build-google-auto__full_gold | 1.0 | pass |
| control | fix-build-google-auto__original | 1.0 | pass |
| control | flink-query__all_faults | 0.0 | fail |
| control | flink-query__full_gold | 0.0 | fail |
| control | flink-query__original | 0.0 | fail |
| control | manufacturing-equipment-maintenance__all_faults | 1.0 | pass |
| control | manufacturing-equipment-maintenance__full_gold | 0.0 | fail |
| control | manufacturing-equipment-maintenance__original | 1.0 | pass |
| control | pddl-airport-planning__full_gold | 1.0 | pass |
| control | pddl-airport-planning__original | 1.0 | pass |
| control | sec-financial-report__all_faults | 1.0 | pass |
| control | sec-financial-report__full_gold | 1.0 | pass |
| control | sec-financial-report__original | 1.0 | pass |
| control | single-fix-build-google-auto-RI-001__condition_baseline | 1.0 | pass |
| control | single-fix-build-google-auto-RI-002__condition_baseline | 1.0 | pass |
| control | single-flink-query-RI-001__condition_baseline | 0.0 | fail |
| control | single-flink-query-RI-002__condition_baseline | 0.0 | fail |
| control | single-manufacturing-equipment-maintenance-RI-001__condition_baseline | 1.0 | pass |
| control | single-manufacturing-equipment-maintenance-RI-002__condition_baseline | 1.0 | pass |
| control | single-sec-financial-report-RI-001__condition_baseline | 1.0 | pass |
| control | single-sec-financial-report-RI-002__condition_baseline | 1.0 | pass |
| control | single-sec-financial-report-RI-003__condition_baseline | 1.0 | pass |
| control | single-video-silence-remover-RI-001__condition_baseline | 0.0 | fail |
| control | single-video-silence-remover-RI-002__condition_baseline | 0.0 | fail |
| control | single-video-silence-remover-RI-003__condition_baseline | 1.0 | pass |
| control | video-silence-remover__all_faults | 0.0 | fail |
| control | video-silence-remover__full_gold | 0.0 | fail |
| control | video-silence-remover__original | 0.0 | fail |
