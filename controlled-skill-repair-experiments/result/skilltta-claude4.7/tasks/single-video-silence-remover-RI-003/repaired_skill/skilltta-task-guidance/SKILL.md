---
name: skilltta-task-guidance
description: Temporary guidance skill for the Video Silence Remover task. Provides a disciplined workflow for detecting unnecessary opening frames and long silent pauses, cutting them out with ffmpeg, and emitting a strictly-formatted compression_report.json. Emphasizes correct threshold tuning and math consistency.
---

# Task Guidance: Video Silence Remover

## Goal
Produce two deliverables in the current workspace:
1. `compressed_video.mp4` — input video with opening + long silences removed.
2. `compression_report.json` — annotations following the exact schema in the prompt.

## Hint Interpretation
The location hint points at:
- `pause-detector/SKILL.md` → `threshold_ratio` parameter description
- Corresponding tuning notes in `silence-detector` and `video-processor`

Treat this as a signal that **`threshold_ratio` is being misused or miscalibrated**. Common failure modes to check and fix:
- `threshold_ratio` is interpreted in the wrong units (e.g., linear amplitude vs dBFS, or fraction of mean vs fraction of max).
- The ratio is applied before/after noise-floor normalization inconsistently across the three skills.
- Default value is too aggressive (cuts teaching speech) or too lax (misses pauses).
- Minimum-silence-duration gate (>2s) is not enforced, so short natural pauses get cut.

When editing the Skill docs/code:
- Clearly define `threshold_ratio` as: *fraction of the audio's reference level (e.g., median or peak RMS) below which a frame is considered silent*. Document the reference explicitly.
- Ensure all three skills (`pause-detector`, `silence-detector`, `video-processor`) use the **same definition and same reference level**.
- Document sane defaults, e.g., `threshold_ratio ≈ 0.03–0.05` of peak RMS, or equivalently ~ -30 to -35 dBFS, combined with `min_silence_duration = 2.0s`.

## Recommended Pipeline
1. **Probe duration**: `ffprobe -v error -show_entries format=duration -of csv=p=0 data/input_video.mp4`.
2. **Extract audio** to mono WAV 16kHz for analysis (ffmpeg).
3. **Detect silences** with `ffmpeg -af silencedetect=noise=-30dB:d=2` OR a Python RMS-window scan. Parse `silence_start` / `silence_end`.
4. **Detect opening**: assume first teaching speech begins at the first non-silent segment after t=0 that lasts > ~1s. The interval `[0, first_speech_start]` is the opening to remove (even if under 2s).
5. **Build keep-segments** = complement of removed segments.
6. **Cut & concat** using ffmpeg `-filter_complex` with `trim` + `atrim` + `concat`, re-encoding (`libx264` + `aac`) for frame-accurate cuts.
7. **Compute metrics** and write JSON.

## JSON Schema (must match exactly)
```json
{
  "original_duration_seconds": <number>,
  "compressed_duration_seconds": <number>,
  "removed_duration_seconds": <number>,
  "compression_percentage": <number>,
  "segments_removed": [
    {"start": <number>, "end": <number>, "duration": <number>}
  ]
}
```

### Math Consistency (critical, from eval criterion 5)
- `removed_duration_seconds == sum(seg.duration for seg in segments_removed)` (within 0.05s).
- `original_duration_seconds ≈ compressed_duration_seconds + removed_duration_seconds`.
- `compression_percentage = removed_duration_seconds / original_duration_seconds * 100` (rounded to 1–2 decimals).
- Each segment: `duration == end - start`, `start < end`, segments sorted and non-overlapping.

## Patterns Borrowed From Retrieved Examples
- **Validate inputs first** (like BigCodeBench/175 checks for required columns): verify `data/input_video.mp4` exists and ffprobe returns a duration before proceeding; otherwise emit an empty-segments report rather than crashing.
- **Filter empty/degenerate items** (like BigCodeBench/54 ignores empty sentences): drop silence segments shorter than 2s (except the opening) and merge segments whose gap < 0.3s to avoid tiny cuts that hurt playback.
- **Write JSON via `os.path.join(os.getcwd(), ...)` with `json.dump`** (like BigCodeBench/265): keeps output path deterministic in the current workspace, and use native Python floats (not numpy scalars) so `json.dump` serializes cleanly.

## Tuning Checklist for `threshold_ratio`
- [ ] Units documented (linear ratio of RMS vs dB).
- [ ] Reference level documented (peak RMS, median RMS, or absolute dBFS).
- [ ] Same definition used in `pause-detector`, `silence-detector`, `video-processor`.
- [ ] Default tested on ~10-min teaching video; yields plausible 10–30% compression.
- [ ] Combined with `min_silence_duration >= 2.0s` to protect natural speech rhythm.
- [ ] Opening cut handled by a separate rule, not by `threshold_ratio` alone.

## Guardrails
- Do not remove segments that would cut teaching speech; prefer under-cutting to over-cutting.
- Keep total runtime well under 10 minutes; prefer a single ffmpeg concat pass over per-segment re-encodes.
- Always re-probe the output file to populate `compressed_duration_seconds` from the actual file, not from arithmetic, then reconcile against the arithmetic value.
