---
name: skilltta-task-guidance
description: Temporary guidance for the video silence/opening remover task, focusing on robust silence detection, correct interval-merging semantics, and consistent compression reporting.
---

# Task Guidance: Video Silence Remover

## Goal
Produce `compressed_video.mp4` and `compression_report.json` by removing (a) the unnecessary static/noisy opening and (b) long silent pauses (> 2s), while preserving teaching content.

## Pipeline
1. Probe duration with `ffprobe` (seconds, float).
2. Extract mono 16 kHz WAV: `ffmpeg -i input_video.mp4 -ac 1 -ar 16000 -vn tmp.wav`.
3. Detect silence with `ffmpeg -af silencedetect=noise=-30dB:d=0.5` and parse `silence_start`/`silence_end` pairs. Lower threshold (e.g. -35 dB) if too little is detected, raise (e.g. -25 dB) if too much.
4. Detect the opening: look for a leading region (first ~30–60s) that is either silent or has near-constant frames. For audio-only heuristic, treat any silent/low-energy run that starts at (or very near) t=0 as part of the opening and extend `end` to the first speech onset.
5. Build the **removal interval list**:
   - Include opening removal `[0, speech_start]` only if `speech_start > 1.0s`.
   - Include every silent run with `duration > 2.0s`. Trim 0.15–0.25s padding on each side so cuts don’t clip speech.
6. Merge/clean intervals (see Interval Merging below).
7. Build keep intervals = complement of removal within `[0, duration]`.
8. Cut and concatenate with ffmpeg (prefer re-encode for frame-accurate cuts):
   - Use `-ss`/`-to` per segment + concat demuxer, or a single `select`/`aselect` filter with `setpts`/`asetpts`.
9. Write report JSON with the exact schema requested.

## Interval Merging Convention (critical)
The `segment-combiner` convention and `video-processor` checks must agree:
- Intervals are **half-open `[start, end)`** in seconds, floats.
- Sort by `start` ascending.
- Merge two intervals when `next.start - current.end <= GAP_EPS` (use `GAP_EPS = 0.2s`). Do NOT merge only on strict overlap; small gaps between adjacent silences should coalesce so you don't leave sub-second speech islands.
- After merging, drop any interval with `duration < MIN_REMOVE = 2.0s` (except the opening removal, which is always kept if present).
- Clamp to `[0, total_duration]`; discard empty/negative intervals.
- Validate: for every consecutive pair `a, b` ensure `a.end < b.start` (strictly), otherwise re-merge.

## Consistency Checks (video-processor side)
Before writing output, assert:
- `sum(keep_durations) + sum(removed_durations) ≈ original_duration` within 0.5s.
- `compressed_duration ≈ sum(keep_durations)` within 0.5s (measure with ffprobe on the output too).
- `compression_percentage = removed / original * 100`, rounded to 2 decimals.
- Each reported segment satisfies `end > start`, `duration == end - start`, and segments are non-overlapping and sorted.
- Expected compression for a ~10 min teaching video is typically 5–30%. If outside, re-tune `silencedetect` threshold rather than silently shipping.

## Report Schema (exact keys)
```json
{
  "original_duration_seconds": 0,
  "compressed_duration_seconds": 0,
  "removed_duration_seconds": 0,
  "compression_percentage": 0,
  "segments_removed": [
    {"start": 0, "end": 0, "duration": 0}
  ]
}
```
All numbers are floats (seconds); `compression_percentage` is a percentage number (e.g. 12.34), not a ratio.

## Patterns Borrowed From Prior Examples
- **Schema-first JSON writing** (like the dict→JSON example): assemble a plain dict with the required keys and `json.dump` it; don’t post-hoc patch the file.
- **Filter-then-aggregate** (like the DataFrame filtering examples): first filter raw silence events by `duration > 2s` and opening rule, then aggregate/merge, then compute summary stats — never compute stats on unfiltered events.
- **Guard empty inputs**: if no silence events survive filtering, still emit a valid report with `segments_removed: []` and `compressed_duration == original_duration`, and copy the input video to `compressed_video.mp4`.

## Common Pitfalls to Avoid
- Using closed intervals `[a, b]` on one side and half-open on the other → double-counted frames and `original ≠ compressed + removed`.
- Merging only on overlap: leaves 0.3–1.5s speech slivers between back-to-back silences, causing audible stutter.
- Forgetting to clamp the final interval to `total_duration` (silencedetect sometimes reports `silence_end` beyond EOF).
- Using stream copy (`-c copy`) for cuts: keyframe snapping desyncs audio/video; prefer re-encode or use `-avoid_negative_ts make_zero` with concat demuxer on re-encoded parts.
- Reporting `compression_percentage` as a 0–1 ratio instead of 0–100.
