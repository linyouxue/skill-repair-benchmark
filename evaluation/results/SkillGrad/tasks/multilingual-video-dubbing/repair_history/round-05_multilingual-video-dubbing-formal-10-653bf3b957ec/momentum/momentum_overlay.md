### [multilingual-video-dubbing] Run ended without producing any required /outputs deliverables
- signal: failure
- pattern: deliverables-gate-before-termination
- anchor: deliverables-gate
- gap: The executor terminated (end_turn) without a final artifact-production phase and without an unconditional pre-termination deliverables check. The output inventory contained only provided inputs—none of the required paths existed (at minimum `/outputs/tts_segments/seg_0.wav`, `/outputs/dubbed.mp4`, `/outputs/report.json`). This shows the “Deliverables Gate (block end-turn)” instruction present across multiple skills is not being invoked as a hard termination interceptor.
- proposed_change: Strengthen the executor workflow so `deliverables-gate` is executed unconditionally as the last step before end_turn, independent of which skill was selected. In L2, add an explicit “pre-end_turn hook” checklist: (1) `mkdir -p /outputs/tts_segments`, (2) generate/write each artifact, then (3) `ls -la /outputs /outputs/tts_segments`, (4) `ffprobe` the WAV and MP4, (5) `python -c 'json.load(open(...))'` for the report; if any check fails, branch back to the producing step and re-run the hook until it passes.

## WORKFLOW-THEMES

- (none this iteration)
