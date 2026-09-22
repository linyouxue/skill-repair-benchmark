### [Task video-silence-remover] Missing output artifact creation (no deliverables written)
- signal: failure
- pattern: produce-required-deliverables-and-verify
- anchor: materialize-deliverables
- gap: The run ended with `stop_reason: end_turn` and `n_skill_invocations: 0`, and the workspace/output inventory contained only the input video. The executor did not run any part of the end-to-end pipeline (audio extraction → energy calculation → silence/pause detection → segment combining → video processing → report generation) and did not execute the required deliverables verification gate (existence of `compressed_video.mp4` and `compression_report.json`).
- proposed_change: Strengthen the workflow gate at `materialize-deliverables` to be *unskippable* at the orchestrator level: before end_turn, require (1) explicit inventory of required filenames, (2) execution of the minimal pipeline that writes them (at least `video-processor` + `report-generator`, with prior steps as needed to produce segments), and (3) a final file-existence + JSON-parse + required-keys check matching `references/materialize-deliverables.md`. Add a final “workspace inventory must include both exact filenames” checklist item.

## WORKFLOW-THEMES

- (none this iteration)
