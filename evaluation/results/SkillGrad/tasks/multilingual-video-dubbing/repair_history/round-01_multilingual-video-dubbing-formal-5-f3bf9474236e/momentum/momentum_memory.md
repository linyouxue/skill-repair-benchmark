### deliverables-gate-before-termination | workflow | block end-turn until all required output artifacts exist at exact paths
- anchor: (none yet)
- appeared_in: iter_0
- description: The executor can reach the end of the run without producing any of the required deliverables, yielding an empty output inventory. This indicates a missing or weak finalization step: there is no enforced “deliverables gate” that checks for required files (and their locations) before termination. In the multilingual-video-dubbing task, the required artifacts include a TTS segment WAV at an exact path (e.g., /outputs/tts_segments/seg_0.wav), a muxed dubbed video (/outputs/dubbed.mp4), and a structured report (/outputs/report.json). Without a gate, the agent may stop after planning or partial progress, even if nothing was written.
- latest_executor_action: Before ending a run, verify all required deliverables exist at the exact required paths; if any are missing, continue execution to create them (including creating parent directories). After writing, re-check existence and (when feasible) basic metadata sanity (e.g., WAV is readable, MP4 has audio stream, JSON parses). Do not terminate until the inventory matches requirements.
- remedy_log:
  - iter_0 | diagnosis: run ended with empty output inventory; none of /outputs/tts_segments/seg_0.wav, /outputs/dubbed.mp4, /outputs/report.json were produced
            | patch: (none yet; record bootstrap from batch diagnosis)
