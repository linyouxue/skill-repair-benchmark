### [multilingual-video-dubbing] run terminated with no /outputs artifacts despite extensive tool activity
- signal: failure
- pattern: deliverables-gate-before-termination
- anchor: deliverables-gate
- gap: Despite 46 tool calls, the executor reached end_turn with none of the required files present: `/outputs/tts_segments/seg_0.wav`, `/outputs/dubbed.mp4`, `/outputs/report.json`. This indicates the end-of-run “Deliverables Gate (block end-turn)” was not invoked (or was ignored) as a hard stop condition; the run did not even create `/outputs/` subfolders or perform a final `ls -la /outputs` + `ffprobe` + JSON-parse verification.
- proposed_change: Add/strengthen an always-on workflow hook: immediately before any termination/final answer, run the deliverables-gate procedure (create dirs, check existence, check readability) and loop back to artifact production on any missing/unreadable file. This hook must run even if no domain skill was explicitly selected, and even after long tool sequences.

## WORKFLOW-THEMES

- (none this iteration)
