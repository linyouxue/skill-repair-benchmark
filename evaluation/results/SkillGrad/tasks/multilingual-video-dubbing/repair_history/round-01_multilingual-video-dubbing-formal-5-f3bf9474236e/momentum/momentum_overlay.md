### [multilingual-video-dubbing] outputs never produced; agent terminated with empty output inventory
- signal: failure
- pattern: deliverables-gate-before-termination
- anchor: (none)
- gap: The trajectory ended without creating any required artifacts; there is no workflow-level “deliverables gate” that blocks termination until required files are written at the exact paths. Concretely, the run produced an empty output inventory `[]` instead of /outputs/tts_segments/seg_0.wav, /outputs/dubbed.mp4, and /outputs/report.json.
- proposed_change: Add an explicit pre-submit validation + retry loop to the dubbing workflow guidance: (1) ensure /outputs and /outputs/tts_segments directories exist; (2) force creation of seg_0.wav with required export properties (e.g., 48kHz mono WAV) and basic readability check; (3) mux dubbed audio with original video to /outputs/dubbed.mp4 and verify MP4 contains expected video+audio streams; (4) write /outputs/report.json and validate it parses and includes required fields; (5) only allow end-turn after `ls`/file-existence checks confirm all deliverables are present.

## WORKFLOW-THEMES

- (none this iteration)
