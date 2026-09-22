### [video-silence-remover] ended run without producing required `compressed_video.mp4` and `compression_report.json`
- signal: failure
- pattern: produce-required-deliverables-and-verify
- anchor: materialize-deliverables
- gap: Despite existing guidance in `video-processor` ("Workflow: Finish With Verified Deliverables") and the L3 algorithm `references/materialize-deliverables.md`, the executor still terminated (`stop_reason="end_turn"`) with no artifact creation step: the workspace contained only the input video and neither required output file was written. This indicates the deliverables gate is not being treated as a hard termination precondition (no final workspace inventory, no existence/size checks, no JSON parse/schema validation).
- proposed_change: Strengthen the orchestrator-facing termination discipline: require an explicit final "termination precondition" checklist that lists both required filenames and the result of existence/size/parse checks (PASS required for all). Additionally, add an instruction that if the run has not invoked the pipeline steps that *write* `compressed_video.mp4` and `compression_report.json`, it must immediately run the minimal end-to-end pipeline (video-processor render → report-generator) and then re-run the deliverables gate; never end the turn without recorded PASS results.

## WORKFLOW-THEMES

- (none this iteration)
