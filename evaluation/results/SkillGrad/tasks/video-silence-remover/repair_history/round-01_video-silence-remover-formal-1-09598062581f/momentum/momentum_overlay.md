### [video-silence-remover] missing required artifacts: `compressed_video.mp4` and `compression_report.json`
- signal: failure
- pattern: produce-required-deliverables-and-verify | new
- anchor: (none)
- gap: The run reached `end_turn` without any step that writes the required deliverables; assessment shows Output inventory: `[]`. There is no workflow checkpoint that forces producing `compressed_video.mp4` and `compression_report.json` and then verifying they exist / are non-empty / JSON parses before finishing.
- proposed_change: Add a mandatory final checkpoint to the top-level workflow guidance (or video-processor/report-generator wrapper): (1) run the minimal pipeline to generate `compressed_video.mp4`; (2) write `compression_report.json` in the required schema (durations, removed segments); (3) verify outputs exist and validate JSON parse+keys; block `end_turn` until checks pass.

## WORKFLOW-THEMES

- (none this iteration)
