### [multilingual-video-dubbing] terminated without producing required /outputs artifacts
- signal: failure
- pattern: deliverables-gate-before-termination
- anchor: deliverables-gate
- gap: The run hit the final end_turn termination without running the Deliverables Gate and while required output paths were still absent/unverified—most critically `/outputs/dubbed.mp4`, `/outputs/report.json`, and `/outputs/tts_segments/seg_0.wav`. This is explicitly contrary to the existing rule “Deliverables Gate (block end-turn)” (e.g., in `text-to-speech/SKILL.md`: “Immediately before ending the run, verify that every required artifact exists at the exact required path...; if not, do not terminate”).
- proposed_change: Strengthen the workflow binding so the deliverables gate is executed unconditionally as the last step before any end_turn, not only when a specific skill is selected. Concretely: add/upgrade an always-on L2 workflow hook that (1) enumerates required paths early, (2) `mkdir -p` for parent dirs, (3) performs `ls -la /outputs` + ffprobe/JSON parse checks, and (4) loops back to artifact production until the L3 `references/deliverables-gate.md` procedure passes.

## WORKFLOW-THEMES

- (none this iteration)
