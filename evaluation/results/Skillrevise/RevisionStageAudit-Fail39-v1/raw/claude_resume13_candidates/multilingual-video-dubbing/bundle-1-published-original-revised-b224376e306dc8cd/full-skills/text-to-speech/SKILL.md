# Multilingual TTS Dubbing Pipeline

## Purpose
Produce dubbed audio aligned to timed segments (e.g., SRT windows) over a target video, using a neural TTS engine, with verifiable placement precision, drift bounds, and a schema-conformant report artifact.

## When to Use
Trigger when the task requires generating per-segment speech aligned to a timing file and a target video, delivering both audio and a structured report describing placement, duration control, and drift per segment.

## Procedure
- Discover inputs and environment: use `ffprobe` on the target video to read duration, sample rate, and channel count; parse the timing file (e.g., SRT) into segments with `window_start`, `window_end`, and text; read acceptance criteria to extract loudness target, drift tolerance, placement precision, and allowed `duration_control` values; if any are unspecified, default to |drift_sec| <= 0.2s and placed_start precision <= 10 ms.
- Validate TTS engine before committing: enumerate available neural TTS options (offline model or cloud) in the environment; synthesize a short probe clip and confirm it is voiced (non-trivial spectral energy above ~4 kHz); if only a formant synthesizer (e.g., espeak-ng) is available, STOP and report a quality-gate failure instead of silently falling back.
- Synthesize per segment with the chosen engine at its native sample rate; record engine identity and sample rate; resample/mix to match the video's audio properties only once, as a final step.
- Place each segment: compute required duration = `window_end - window_start`; choose `duration_control` by rule - if synthesized length is within tolerance, place as-is; if shorter, `pad_silence`; if slightly longer (within a small ratio), `rate_adjust`; if far longer, `trim` with boundary fades. Set `placed_start = window_start` with precision <= 10 ms; apply short fades at boundaries to avoid clicks.
- Normalize and verify: measure integrated loudness and normalize to the task-declared target (do not assume a value); then reload `report.json` and assert required fields exist, `duration_control` is within the declared enum, `|placed_start - window_start| <= 0.01s`, and `drift_sec = placed_end - min(window_end, video_duration)` with `|drift_sec| <= 0.2s`. Log and fail on any segment that violates these.

## Constraints / Pitfalls
- Do not use formant/prototyping TTS (e.g., espeak-ng) for final delivery; neural engines only. If none are available, fail loudly rather than degrade quality.
- Do not hardcode loudness, filter, or fade literals; derive loudness target from the task spec and apply cleanup only if required by the acceptance criteria. Always compute drift against `min(window_end, video_duration)`, not the raw window end, and re-normalize after any tempo change.