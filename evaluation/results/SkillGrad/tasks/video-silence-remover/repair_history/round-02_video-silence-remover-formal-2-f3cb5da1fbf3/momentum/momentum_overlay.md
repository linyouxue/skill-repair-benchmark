### [video-silence-remover] missing end-to-end execution produced no required deliverables
- signal: failure
- pattern: produce-required-deliverables-and-verify
- anchor: materialize-deliverables
- gap: The run terminated immediately (`termination_reason: end_turn`) without invoking any skills (`n_skill_invocations: 0`) and without writing any required artifacts; neither `compressed_video.mp4` nor `compression_report.json` exists in the workspace (only the original input video is present). The workflow-level “finish with verified deliverables” gate was not executed.
- proposed_change: Strengthen the orchestration rule to be blocking: before `end_turn`, inventory required deliverables and then run the minimal full pipeline (audio-extractor → energy-calculator → silence-detector + pause-detector → segment-combiner → video-processor to write `compressed_video.mp4` → report-generator to write `compression_report.json`), then execute the L3 verification procedure in `video-processor/references/materialize-deliverables.md` (existence/non-empty + JSON parse + required keys). If any check fails, fix the smallest upstream cause and re-run verification.

## WORKFLOW-THEMES

- (none this iteration)
