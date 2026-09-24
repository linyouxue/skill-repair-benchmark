---
name: skilltta-task-guidance
description: Task-specific operational guidance synthesized at test time from retrieved training examples.
---

# SKILL.md

## When to use
Use this skill when the target task provides a media file (video/audio) and asks you to detect and remove low-information segments (silence, static openings, long pauses), then produce both a processed media artifact and a structured JSON report describing what was removed. The binding contract for this class of task typically requires:
- A processed output file at a specified workspace path.
- A JSON report with a fixed schema documenting original/compressed/removed durations, a compression percentage, and a list of removed segments with start/end/duration.
- Internal arithmetic consistency (original ≈ compressed + removed).
- Preservation of substantive content while trimming an opening and long pauses above some threshold.

Before acting, gather:
- Exact input path, exact output filenames, and the exact JSON schema keys/types from the task prompt.
- The pause-length threshold and any qualitative guidance about the opening (e.g., static frames, noise).
- Time/compute limits mentioned (e.g., must finish under a stated wall-clock budget).
- Available tools in the environment (ffmpeg, ffprobe, Python audio libs).

## Possible Failure Modes
- Schema drift: renaming keys, nesting differently, or omitting required fields like `compression_percentage` or per-segment `duration`.
- Inconsistent arithmetic: `original_duration_seconds` not ≈ `compressed_duration_seconds + removed_duration_seconds`, or `compression_percentage` computed against the wrong base.
- Overly aggressive silence detection that cuts speech pauses shorter than the stated threshold, removing teaching content.
- Overly conservative detection that leaves the static opening or long pauses intact, yielding too-low compression.
- Detecting silence only by video (dark/static frames) or only by audio when the opening is characterized by both static video and noisy audio — missing one signal.
- Reporting segments in the compressed timeline rather than in original-video time coordinates.
- Merging adjacent silent segments incorrectly (or not at all), producing many tiny cuts and audible glitches.
- Re-encoding with a slow codec / high quality settings that blow the runtime budget, or using stream copy across cut points and getting keyframe-misaligned output.
- Off-by-one/precision issues: writing integer seconds when floats are expected, or float noise causing the sum check to fail.
- Writing outputs to the wrong directory (not the current workspace) or with slightly different filenames than required.
- Leaving temp files or partially written JSON if the pipeline errors midway.

## Possible procedures
1. Probe the input:
   - Use `ffprobe` to get exact duration, streams, sample rate, and codec.
   - Extract audio (mono, e.g., 16 kHz WAV) for analysis; keep the original for final cutting.

2. Detect the opening:
   - Use audio energy/RMS over a sliding window and/or `ffmpeg -af silencedetect` from t=0 to find the first sustained speech onset.
   - Optionally corroborate with a video signal (frame-difference or scene score) to confirm static frames at the start.
   - Trim from 0 up to shortly before the first confident speech onset; avoid cutting into the first spoken words (leave a small pad, e.g., 0.2–0.5s).

3. Detect long pauses:
   - Run silence detection with a threshold and minimum-duration parameter matched to the task’s pause criterion (e.g., > the stated seconds).
   - Sensible starting points: noise floor around -30 to -35 dB, min silence duration equal to (or slightly above) the task threshold.
   - Merge overlapping/adjacent silence intervals; add a small keep-pad on each side so speech isn’t clipped.

4. Build the removal plan in original-time coordinates:
   - Produce a list of `[start, end]` segments to remove (opening + long pauses), sorted and non-overlapping.
   - Compute keep segments as the complement within `[0, original_duration]`.

5. Cut and concatenate:
   - Prefer ffmpeg with a single filter graph (`select`/`atrempo`-free `aselect` + `setpts`/`asetpts` and `concat`) or generate segment files and concat-demux them.
   - Re-encode with a fast but reasonable codec (e.g., libx264 `-preset veryfast`, AAC audio) to guarantee clean cuts and stay within the time budget.
   - Verify the output file plays and has expected duration via `ffprobe`.

6. Emit the JSON report:
   - Use exactly the keys and nesting shown in the prompt.
   - Populate durations from measured values: `original_duration_seconds` from ffprobe of input; `compressed_duration_seconds` from ffprobe of output; `removed_duration_seconds` = sum of removed segment durations; `compression_percentage` = removed / original * 100 (confirm which base the prompt implies).
   - Ensure each removed segment includes `start`, `end`, `duration` in original-video seconds, sorted ascending, non-overlapping.
   - Round consistently (e.g., to 2–3 decimals) so the arithmetic check still holds.

7. Sanity checks and recovery:
   - If compression is implausibly high (e.g., > ~50%) or low (~0%), re-tune thresholds and re-run detection rather than shipping.
   - If sum check fails, recompute from the segment list rather than patching numbers.
   - If runtime approaches the budget, switch to faster ffmpeg presets or coarser analysis windows.

## Verification Checklist
- [ ] Both required output artifacts exist at the exact paths/filenames requested, in the current workspace.
- [ ] The processed media file opens, plays, and has a duration matching `compressed_duration_seconds` within a small tolerance.
- [ ] JSON parses and contains every required key with the correct types (numbers as numbers, list of objects for segments).
- [ ] Each removed segment has `start < end`, `duration == end - start`, uses original-video time, and segments are sorted and non-overlapping.
- [ ] `original_duration_seconds ≈ compressed_duration_seconds + removed_duration_seconds` within rounding tolerance.
- [ ] `compression_percentage` matches `removed / original * 100` (or the base specified) after rounding.
- [ ] The opening static/noise region is removed; spot-check that the first frames of output contain real content.
- [ ] Long pauses above the stated threshold are removed while shorter, natural speech pauses are kept.
- [ ] No values, filenames, thresholds, or code were copied verbatim from unrelated retrieved examples; all decisions trace to the target prompt.
- [ ] Unrelated workspace files were not modified or deleted; temp files cleaned up.
- [ ] Total processing time is comfortably under the stated runtime budget; a fallback fast-encode path was used if needed.
