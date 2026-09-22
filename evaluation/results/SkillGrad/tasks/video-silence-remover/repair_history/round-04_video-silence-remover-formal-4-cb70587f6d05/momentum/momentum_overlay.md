### [video-silence-remover] ended without producing required output artifacts
- signal: failure
- pattern: produce-required-deliverables-and-verify
- anchor: materialize-deliverables
- gap: The executor terminated (`end_turn`) without invoking any of the pipeline skills and without materializing the required deliverables (`compressed_video.mp4`, `compression_report.json`). This bypassed the existing deliverables gate in video-processor (“Workflow: Finish With Verified Deliverables”) and the L3 procedure in `references/materialize-deliverables.md` that requires: inventory deliverables → run minimal pipeline that writes them → verify existence/non-empty/JSON schema → only then end.
- proposed_change: Strengthen the L2 deliverables gate to include a hard, externally-visible “termination precondition”: before `end_turn`, explicitly list the deliverables and provide an existence/size/JSON-parse check result (or run a small verification snippet). Also add/clarify an orchestrator-level rule that at least one end-to-end pipeline invocation must occur in any task whose evaluation expects files, and that “no skill invocations” is itself a failing verification signal that must trigger running the pipeline rather than ending.

## WORKFLOW-THEMES

- (none this iteration)
