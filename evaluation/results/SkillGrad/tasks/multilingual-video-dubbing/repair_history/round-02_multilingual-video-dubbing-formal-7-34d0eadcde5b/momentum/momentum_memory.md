### deliverables-gate-before-termination | workflow | block end-turn until all required output artifacts exist at exact paths
- anchor: deliverables-gate
- appeared_in: iter_0, iter_5
- description: The executor can reach the end of the run without producing any of the required deliverables, yielding an empty output inventory. This indicates a missing or weak finalization step: there is no enforced “deliverables gate” that checks for required files (and their locations) before termination. In the multilingual-video-dubbing task, the required artifacts include a TTS segment WAV at an exact path (e.g., /outputs/tts_segments/seg_0.wav), a muxed dubbed video (/outputs/dubbed.mp4), and a structured report (/outputs/report.json). Without a gate, the agent may stop after planning or partial progress, even if nothing was written.

This recurred even after the TTS skill added an explicit Deliverables Gate section + an L3 algorithm (references/deliverables-gate.md), implying the executor sometimes fails to invoke the skill at all (zero skill invocations) or ignores the gate before end_turn.
- latest_executor_action: Treat file-based deliverables as a hard “stop condition”. Early in the run, enumerate exact required paths and create parent directories. Before end_turn, run the deliverables gate from the TTS skill (anchor: deliverables-gate) to (1) assert existence, (2) assert minimal readability (ffprobe/JSON parse), and (3) if anything is missing/unreadable, branch back to the pipeline step that produces that artifact, then re-run the gate. Do not terminate until the gate passes.
- remedy_log:
  - iter_0 | diagnosis: run ended with empty output inventory; none of /outputs/tts_segments/seg_0.wav, /outputs/dubbed.mp4, /outputs/report.json were produced
            | patch: (none yet; record bootstrap from batch diagnosis)
  - iter_5 | diagnosis: run again ended with no tool actions and no /outputs/* artifacts; executor did not invoke any skill rules (including the existing Deliverables Gate)
            | patch: retarget anchor to existing skill section deliverables-gate + L3 references/deliverables-gate.md; recommend adding a global workflow hook to always run the gate before end_turn, even when no skill was selected
