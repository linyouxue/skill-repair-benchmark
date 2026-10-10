# Dubbing and TTS Audio Mastering With Verifier-Aligned Outputs

## Purpose
Produce delivery-ready dubbed audio (often stitched from per-segment TTS) and optionally a muxed media file plus a machine-checked report, while staying robust to environment differences (missing TTS engines, differing ffmpeg capabilities) and verifying timing, loudness, and output artifacts at the exact task-required paths.

## When to Use
Use when a task requires generating TTS for multiple timed segments (SRT/CSV/JSON timing windows), stitching them into a single track, mastering (click prevention, loudness normalization), and delivering verifier-checked artifacts (e.g., final audio/video and a JSON report). Do not use for one-off single-file narration without timing windows or without any required deliverables.

## Procedure
- 1) Contract and input discovery (no writes yet)
- Identify from the task prompt/files: (a) segment definition source (SRT/CSV/JSON), (b) required output artifacts and their exact paths, (c) required audio specs (sample rate, channels), (d) timing tolerances, (e) loudness target and measurement method, (f) any report schema requirement.
- If any of (a)-(f) are ambiguous, stop and request clarification or infer only from locally present task files (do not guess hidden paths/specs).
- 2) Environment and tool discovery checkpoint (execution anchor)
- Discover available tools before committing to a pipeline:
- Find ffmpeg and ffprobe (or equivalents) and record their versions and executable paths.
- Enumerate available TTS backends locally (examples: offline CLI engines, local libraries, or an existing project script). Select the best available backend using a deterministic order: prefer local/offline first if network is uncertain; otherwise choose the highest quality available.
- Check loudness measurement support: prefer an ITU-R BS.1770 meter that exists in the current ffmpeg build (e.g., ebur128). If loudnorm options differ, adapt by using a measurement mode that is actually supported, or fall back to ebur128-based measurement plus gain adjustment.
- Evidence to capture: command outputs showing tool presence/capabilities and a recorded chosen backend plus fallback list.
- 3) Parse and validate segment windows (schema gate)
- Load segments and validate minimally:
- Each segment has a start time, end time, and text (or a resolvable reference).
- Assert start < end, monotonic ordering (or define tie-breaking), and no negative times.
- Record required per-segment metadata you will later report (segment id/index, window start/end).
- If the segment file is malformed or missing required fields, stop and repair the input file or request clarification (do not generate audio from partial parses).
- 4) Per-segment synthesis to a consistent intermediate format
- For each segment:
- Synthesize speech to an intermediate audio file using the selected TTS backend.
- Immediately probe the generated file for readability, duration, sample rate, and channels.
- Convert to a consistent working format for stitching (choose based on discovered environment, but ensure you can later meet the final required output specs).
- Fail fast if any segment audio is empty/unreadable; switch to the next fallback TTS backend and re-render only the failing segments.
- 5) Placement, duration control, and click-safe boundaries (timing checkpoint)
- For each segment, align audio to its target window:
- If audio is shorter than the window, pad with silence to match window duration.
- If longer, apply gentle duration control within a strict limit (set a small max rate change; if exceeding, escalate: re-synthesize with different speaking rate if supported, or accept truncation only if the task explicitly allows it).
- Apply short fade-in/out at segment boundaries after padding/trimming to prevent clicks.
- Stitch segments onto a single timeline track according to window start times.
- Compute placed_start_sec and placed_end_sec from the actual stitched timeline (not from intended durations) and compute drift vs the window. If any segment violates task timing tolerances, iterate: adjust duration strategy or re-synthesize.
- 6) Mastering and final media build (then verify) (execution anchor)
- Only after timing is final:
- Apply cleanup filters only if they are supported in the current environment and do not change timing.
- Perform loudness measurement using the discovered available method, then apply normalization to the task target (if specified). If any processing changes duration, repeat timing validation.
- If producing a muxed video/media file, mux audio with the original media using a method supported by the environment, then probe the final media:
- Verify final audio stream sample rate and channels match the task spec (e.g., 48000 Hz, mono).
- Re-check timing drift using actual rendered durations (accounting for any encoder/mux behavior) and ensure it meets tolerances.
- 7) Output grounding and report validation (execution anchor)
- Write required artifacts to the exact task-specified output paths (do not silently redirect).
- For each required output path:
- Check file exists, is readable, and is non-empty (or otherwise meets the task-declared expectation).
- If a write fails, diagnose mounts/permissions and supported write locations; rerun only the minimal preceding step needed to regenerate.
- If a JSON report is required:
- Reload it and validate against the task-declared schema: required keys present, types correct, arrays/objects shaped as expected, and numeric fields are finite.
- Ensure report timing and loudness values are derived from measured artifacts (probes/measurements), not from intended settings.

## Constraints / Pitfalls
- Do not assume specific tools (e.g., a particular cloud TTS package) or specific ffmpeg options exist; always discover tool availability and supported capabilities before choosing commands, and define a deterministic fallback order.
- Do not claim success until you have (a) probed the final produced artifact(s) for stream properties and (b) verified existence/readability at the exact task-required output paths; avoid silent path changes, and avoid timing/loudness assertions based only on intended settings rather than measured results.