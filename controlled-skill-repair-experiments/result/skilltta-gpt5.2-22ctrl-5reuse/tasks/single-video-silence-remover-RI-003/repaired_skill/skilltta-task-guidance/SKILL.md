---
name: skilltta-task-guidance
---

# SkillTTA Task Guidance: Video Silence Remover

## Goal
Given `data/input_video.mp4` (~10 minutes), produce:
1. `compressed_video.mp4`: remove (a) unnecessary opening and (b) long pauses (typically `> 2s`) while preserving teaching content.
2. `compression_report.json`: consistent math and valid removed segments.

This guidance focuses on **robust silence/pause detection**, **parameter tuning** (notably `threshold_ratio`), and **safe segment editing**.

---

## High-level workflow
1. **Probe input**: duration, audio presence, sample rate.
2. **Detect silence candidates** using audio energy (preferred) + optional opening heuristic.
3. **Post-process segments**: merge/clean, apply padding, ensure monotonic non-overlapping intervals.
4. **Cut and concatenate** using ffmpeg (fast, accurate) into `compressed_video.mp4`.
5. **Generate report** with consistent durations and segment list.

---

## Step 1 — Probe video (validation pattern)
Follow the “validate inputs first” pattern:
- Verify file exists.
- Get duration from `ffprobe`.
- Detect if an audio stream exists; if not, fall back to a *visual* heuristic for opening only (or skip pause removal).

Recommended commands:
- Duration:
  - `ffprobe -v error -show_entries format=duration -of default=nk=1:nw=1 input.mp4`
- Audio stream check:
  - `ffprobe -v error -select_streams a:0 -show_entries stream=codec_type -of csv=p=0 input.mp4`

Guardrails:
- If duration is missing/0, fail early.
- If no audio, do not attempt audio silence detection; only remove a short opening if clearly static (optional).

---

## Step 2 — Silence detection (audio-first)
### Preferred detector: `ffmpeg silencedetect`
Run silencedetect on the audio:
- `ffmpeg -i input.mp4 -af "silencedetect=noise=-35dB:d=2.0" -f null - 2> silencedetect.log`

Interpretation:
- `noise` controls threshold.
- `d` is the minimum silence duration (use `2.0` seconds per task).

### Dynamic thresholding via `threshold_ratio` (important)
In many teaching videos, the “opening” can be low-level noise or music; a fixed dB threshold may under-detect or over-detect.

Use a **relative** threshold strategy:
1. Compute a baseline loudness/energy of the track (e.g., median RMS over short windows).
2. Define silence threshold as:
   - `silence_threshold = baseline_energy * threshold_ratio`

**How to interpret `threshold_ratio`:**
- Larger `threshold_ratio` ⇒ threshold closer to baseline ⇒ **more aggressive** silence detection (more removed).
- Smaller `threshold_ratio` ⇒ threshold lower ⇒ **less aggressive** (keeps more content).

Recommended starting ranges:
- Typical: `threshold_ratio = 0.10 ~ 0.25`
- Noisy background: try `0.05 ~ 0.15`
- Very clean mic: can go up to `0.25 ~ 0.35`

Tuning heuristic (fast iteration):
- If it removes speech: **decrease** `threshold_ratio` (or lower `noise` aggressiveness / increase padding).
- If it misses long pauses: **increase** `threshold_ratio` (or raise `noise` / reduce `d` slightly but keep `>=2s` if possible).

### Opening removal heuristic
Openings are often static frames + low/constant noise.
Implement at least one of:
- **Leading silence rule**: if the first detected silence starts near `t=0` and lasts `>= 1.5~3s`, mark it removable.
- **Low-energy intro window**: if the first `N` seconds have energy consistently below threshold (e.g., 80% of frames/windows below threshold), remove that region.

Do not blindly remove a fixed first X seconds; instead remove only if it meets the silence/low-energy criterion.

---

## Step 3 — Segment post-processing (make cuts safe)
Silence detection often yields many small intervals. Clean them before cutting.

### 3.1 Merge and filter
- Remove only segments with `duration >= 2.0s` (task requirement).
- Merge adjacent/nearby silent segments if the gap between them is small (e.g., `< 0.2s`).

### 3.2 Apply padding to avoid cutting speech
To preserve teaching content, shrink removed segments slightly:
- For each removed segment `[start, end]`, apply:
  - `start' = start + pad_in`
  - `end' = end - pad_out`
- Typical: `pad_in = 0.10~0.20s`, `pad_out = 0.10~0.20s`

Then re-check:
- If `end' <= start'`, drop the segment.

### 3.3 Clamp and validate
Ensure:
- `0 <= start < end <= original_duration`
- Sorted by `start`
- No overlaps (merge if overlaps occur)

This mirrors the “robustness checks” pattern: validate, then proceed.

---

## Step 4 — Produce compressed video (ffmpeg concat)
Convert removed segments into **kept** segments:
- If removed segments are `R = [r1, r2, ...]`, compute kept segments as the complement over `[0, duration]`.

Then cut+concat:
- Create a concat list file (preferred: `-f concat -safe 0`), or use `filter_complex` with `trim`/`atrim`.

Fast, accurate approach (re-encode once):
- For each kept segment, trim video+audio, then concat.

If using stream copy (`-c copy`), cuts may be inaccurate unless keyframes align; for teaching videos, **re-encode** is safer.

Recommended encoding defaults:
- Video: H.264 (`libx264`) CRF ~ 18–23, preset veryfast/fast
- Audio: AAC 128k

---

## Step 5 — Generate `compression_report.json` (math consistency)
Required format:
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

Rules:
- Each segment’s `duration = end - start` (use consistent rounding policy).
- `removed_duration_seconds = sum(segment.duration)`
- `compressed_duration_seconds ≈ original_duration_seconds - removed_duration_seconds`
- `compression_percentage = removed_duration_seconds / original_duration_seconds * 100`

Rounding guidance:
- Keep 2–3 decimal places.
- Ensure the identity holds within a small epsilon (e.g., 0.05s) after rounding.

Validation pattern (before writing JSON):
- If `original_duration_seconds <= 0`, abort.
- If any segment has negative duration or is out of bounds, fix/merge/clamp.

---

## Practical tuning checklist (when results look wrong)
1. **Too much removed (speech cut):**
   - Decrease `threshold_ratio`
   - Lower silence aggressiveness (`noise` lower magnitude, e.g. -40dB instead of -35dB)
   - Increase padding around cuts
   - Increase `d` to require longer silence
2. **Too little removed (pauses remain):**
   - Increase `threshold_ratio`
   - Increase silence aggressiveness (e.g. -30dB instead of -35dB)
   - Reduce padding slightly
   - Merge close silent segments
3. **Opening not removed:**
   - Ensure leading-silence / low-energy intro heuristic is enabled
   - Consider allowing slightly shorter intro removal (e.g., `>=1.5s`) if it’s clearly non-teaching

---

## Output requirements recap
Place under current workspace:
- `compressed_video.mp4`
- `compression_report.json`

Both must be valid; report must match actual editing decisions.
