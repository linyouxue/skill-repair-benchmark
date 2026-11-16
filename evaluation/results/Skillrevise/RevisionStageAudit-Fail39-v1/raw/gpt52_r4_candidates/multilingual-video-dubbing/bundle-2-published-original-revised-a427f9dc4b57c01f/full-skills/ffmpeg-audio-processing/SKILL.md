# Multilingual Video Dubbing With Timing-Accurate Segment Placement (FFmpeg + TTS)

## Purpose
Create a dubbed audio track from per-segment text (and timing), synthesize speech per segment using an environment-supported TTS backend, place segments onto a full-length timeline with millisecond-accurate starts, mux the new audio with the original video (prefer stream copy for video), and emit a verifier-aligned JSON report with timing and drift metrics.

## When to Use
Use this when the task requires end-to-end video dubbing: segment-level TTS generation, precise placement by start times, drift computation, and producing required artifacts (dubbed media plus a JSON report). Do not use for simple audio extraction/normalization-only tasks.

## Procedure
- 1) Discover inputs, outputs, and capabilities (no assumptions)
- Identify task-declared inputs: source video path, segments source (JSON/CSV/SRT/etc.), target languages/voices, and required output paths (do not invent paths).
- Confirm tools:
- Check `ffmpeg` and `ffprobe` are available.
- If using Python, confirm `python` exists and you can write to the working directory.
- Inspect the source media (anchor):
- Run `ffprobe` to list streams and capture: duration, video stream index/codec, audio stream index, audio sample rate/channels.
- Probe required FFmpeg filters (anchor):
- Attempt a no-output run using `loudnorm` and `ebur128` on a short decode; if a filter is missing, record it and plan a fallback (skip loudness targets or use simpler `volume` with measured peak).
- Decision point: If required outputs paths are not provided or ambiguous, stop and request clarification rather than guessing.
- 2) Parse and validate the segment specification
- Load segment metadata (format-agnostic): for each segment require at least:
- an identifier
- target language (or voice)
- text to speak
- intended start time (seconds) and intended end time (seconds) OR start + duration
- Validate:
- times are numeric, finite, non-negative
- end > start
- segments do not exceed overall media duration unless explicitly allowed
- Decision point: If there are overlapping segments, pick one policy explicitly:
- allow overlap (mix)
- or disallow and fail fast
- or resolve by priority rules (must be task-specified)
- 3) Choose a TTS backend with bounded fallbacks (avoid brittle installs)
- Preferred order (stop at first that works):
- Task-provided local TTS binaries or SDK already installed (discover by checking command availability).
- Network TTS only if network access is confirmed and a short synthesis test succeeds.
- Offline TTS CLI engine (if available) for a minimal viable output.
- Strict constraint: Do not attempt system-wide package upgrades in locked environments.
- If Python deps are needed, install to a user-writable location or a project-local venv; if that fails, switch to an installed CLI TTS.
- Execution anchor (micro-test): Synthesize a 1-2 second test phrase and confirm a readable audio file was produced.
- 4) Synthesize per-segment audio assets
- For each segment:
- Generate TTS audio to a temporary per-segment file.
- Convert immediately to a processing invariant:
- PCM WAV, mono, 48 kHz (or the task-required rate), consistent sample format.
- Measure actual segment audio duration.
- Decision point: Duration fit policy per segment (must be explicit):
- If synthesized duration > segment window: either time-stretch within safe bounds (if supported), else trim with a short fade-out.
- If synthesized duration < segment window: pad trailing silence to match window.
- If time-stretch is needed:
- Prefer FFmpeg `rubberband` if present; otherwise use a constrained fallback (e.g., `atempo` within supported range), and cap adjustments to avoid extreme artifacts.
- 5) Loudness/level handling with verification-visible measurements
- If `loudnorm` is available and loudness targets are specified:
- Use a two-pass approach: first pass to measure, second pass to apply with measured values.
- Otherwise:
- Use `ebur128` or `volumedetect` to measure and apply a conservative gain change.
- Keep this step per-segment (for consistency) or on the final mix (for global consistency), but do not do both unless required.
- 6) Build a full-length dubbed timeline with precise placement
- Create a silent bed with exactly the target duration and invariant format (48 kHz mono).
- Place each segment at its intended start time with millisecond precision:
- Use sample-accurate alignment by converting start_sec to samples (start_samples = round(start_sec * sample_rate)).
- Apply delay and mix segments onto the bed; ensure mixing policy matches overlap policy.
- Compute per-segment placement metadata:
- placed_start_sec derived from the actual sample offset used
- drift_sec = placed_start_sec - intended_start_sec
- 7) Generate report.json and validate schema (anchor)
- Write a JSON report that includes, at minimum:
- a `segments` array
- for each segment: id, intended_start_sec, intended_end_sec (or duration), placed_start_sec, drift_sec, and the chosen TTS backend/voice identifiers when available
- Schema gate (must pass before proceeding):
- Reload report.json from disk.
- Assert it is valid JSON.
- Assert `segments` exists and is a list.
- For each segment assert required numeric fields are numbers (not strings) and finite.
- Assert drift thresholds if specified by the task (e.g., abs(drift_sec) <= 0.2); if violated, re-run placement computation rather than silently accepting.
- 8) Mux dubbed audio with original video and perform final grounding checks (anchor)
- Mux policy:
- Copy the original video stream without re-encoding whenever possible.
- Map the dubbed audio as the primary audio track; preserve original audio only if required.
- Final checks (must be against task-declared output paths):
- Confirm output files exist at the exact required paths and are non-empty.
- Run `ffprobe` on the dubbed media to confirm:
- a video stream exists and matches the source codec when stream-copy is intended
- an audio stream exists with expected sample rate/channels
- If any check fails, stop and fix the smallest failing step (do not continue producing new variants in new paths).

## Constraints / Pitfalls
- Never assume network TTS works; always run a short synthesis test first, and fall back to an offline or preinstalled backend on 403/connection failures.
- Do not hard-code paths, stream indices, sample rates, or filter availability; discover them via `ffprobe` and filter probes, and fail fast if task-required outputs/fields are ambiguous.