# TTS Dubbing Workflow

## Purpose
Produce delivery-ready dubbed audio for a video from a timed script (e.g., SRT), using a neural TTS engine, time-fit per segment, loudness-normalize, mux back to video, and emit a verifiable report.

## When to Use
Trigger when a task requires generating spoken audio for a video or timed segments and muxing it into a deliverable. Do not use for pure audio mastering of pre-recorded human speech, or for prototype/debug TTS where naturalness is not required.

## Procedure
- Discover inputs: locate the source video, timed script (SRT/JSON), target language, output path, and any task-specified loudness/drift targets. If targets are not specified, default to BS.1770 integrated loudness and drift <= 0.2 s.
- Engine selection checkpoint: probe the environment for neural TTS engines (e.g., Kokoro, Piper, Edge-TTS, OpenAI TTS) and list voices matching the target language code. Pick the highest-quality available neural engine and record `engine`, `voice`, `lang`, `sample_rate`. If no neural engine is available, stop and report the missing dependency; do not proceed with a formant engine.
- Synthesize per segment: for each script entry, synthesize audio at the engine's native sample rate; keep per-segment WAV plus start/end times.
- Time-fit: match each segment to its target window via (a) small rate adjust (<= ~8%), (b) silence padding if short, (c) careful trim if long. Apply short boundary fades to avoid clicks.
- Loudness-normalize: measure with ebur128, apply loudnorm to the task-specified target as the final audio step; re-normalize if any tempo change happens afterward.
- Mux: combine the dubbed track with the original video stream (copy video codec) to the task-specified output path.
- Verify: confirm output file exists at the specified path; ffprobe shows preserved video stream and expected audio; compute end-to-end drift and loudness; write `report.json` with engine, voice, drift_sec, integrated_loudness, true_peak, and per-segment timing.

## Constraints / Pitfalls
- Hard constraint: never use formant TTS (espeak-ng, pico, flite) for delivery. Only neural engines qualify. Fail loudly rather than silently degrade.
- Do not hard-code paths, voice IDs, or loudness literals; read them from the task spec or discover at runtime.
- Timing success alone is not acceptance: a passing drift check does not imply audio quality is acceptable. Always verify engine class and that the output is muxed to the exact specified path.
- Keep fallback bounded: try alternative neural engines in order; do not expand into generic audio troubleshooting.