### [multilingual-video-dubbing] terminated without producing any required /outputs artifacts
- signal: failure
- pattern: deliverables-gate-before-termination
- anchor: deliverables-gate
- gap: The run ended with an end_turn despite producing zero deliverables; specifically, none of `/outputs/tts_segments/seg_0.wav`, `/outputs/dubbed.mp4`, or `/outputs/report.json` exist. The trace indicates **no tool actions at all**, so the executor never engaged the existing “Deliverables Gate (block end-turn)” rule in the text-to-speech skill (and never executed any ffmpeg/TTS pipeline steps).
- proposed_change: Add a *global* pre-termination hook in L2 (top-level workflow, not tied to a specific skill selection) that always runs the deliverables gate when the task’s rubric is file-path based. Concretely: (1) at start, write down the deliverables checklist + `mkdir -p` for needed dirs; (2) before end_turn, always run the gate checks (existence + ffprobe + JSON parse) from `references/deliverables-gate.md`; (3) if missing, force execution of the pipeline step that produces each artifact and re-run the gate.

## WORKFLOW-THEMES

- (none this iteration)
