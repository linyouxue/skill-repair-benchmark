---
name: skilltta-task-guidance
---

# SkillTTA Task Guidance: Video Silence/Non-Teaching Removal

## Goal
Given `data/input_video.mp4` (≈10 min teaching video), produce:
1. `compressed_video.mp4`: same content but with **unnecessary opening** and **long pauses (typically > 2s)** removed while preserving teaching.
2. `compression_report.json`: durations + exact removed segments with consistent math.

This skill focuses on **robust detection**, **timestamp correctness (esp. smoothing window ↔ time mapping)**, and **report consistency**.

---

## Key principles (transferable patterns)
- **Validate inputs / handle empty results**: if no silence is detected (or detection fails), output a pass-through video and a report with zero removed segments.
- **Do not mutate raw detection lists in-place without copying**: build cleaned/merged segments as a new list to avoid accidental drift.
- **Make math consistent**: `original ≈ compressed + removed` within small tolerance (e.g., ≤ 0.05s).
- **Keep segmentation sane**: segments must be ordered, non-overlapping, clamped to `[0, original_duration]`, and each has `duration = end - start`.

---

## Recommended pipeline

### 1) Probe video duration
Use ffprobe to get accurate durations:
```bash
ffprobe -v error -show_entries format=duration -of default=nk=1:nw=1 data/input_video.mp4
```
Store as `original_duration_seconds`.

### 2) Detect silence candidates (audio-based)
Preferred: `ffmpeg` `silencedetect` (fast, no custom timestamp mapping pitfalls):
```bash
ffmpeg -i data/input_video.mp4 \
  -af silencedetect=noise=-35dB:d=0.3 \
  -f null - 2> silence.log
```
Parse `silence_start:` and `silence_end:` lines into raw silent intervals.

**Notes**
- Adjust `noise` if needed (`-30dB` to `-45dB` typical).
- Keep `d` small (e.g., 0.2–0.5s) so you can later remove only pauses >2s.

### 3) (If using a Python detector) Ensure smoothing window ↔ timestamp mapping is correct
If your silence detector uses a moving average / smoothing window over frame-wise energy:
- Let `sr` be sample rate, `hop_length` be samples per frame, `i` be frame index (0-based).
- The **frame time** must be:
  - **center time** (recommended):
    `t_center = (i * hop_length + frame_length/2) / sr`
  - If you smooth with a window of `W` frames using a *centered* window, the label time should correspond to the **center** of that window:
    `t = ((i + W//2) * hop_length) / sr` (or equivalent center formula)
- Common bug: using `i/sr` or `i*hop_length/sr` without accounting for **window centering**, causing systematic offsets (segments removed too early/late).

**Actionable rule**: pick one convention (center-of-frame), document it, and apply it consistently when converting indices→seconds for both start and end boundaries.

### 4) Post-process silent intervals into “remove segments”
Steps:
1. **Clamp** each interval to `[0, original_duration]`.
2. **Merge** intervals that are close (e.g., gap ≤ 0.2–0.4s) to avoid choppy edits.
3. **Filter** to remove only meaningful pauses:
   - keep intervals with `duration >= 2.0` seconds (task requirement).
4. **Opening removal**:
   - If the video begins with silence/static, treat an initial silent interval starting near 0s as opening.
   - Practical heuristic: if there is a silent interval with `start <= 0.5` and `duration >= 1.0`, remove it (or extend slightly, e.g., add 0.1–0.2s padding).

**Padding** (optional but helpful): add small padding around removed segments (e.g., `pad = 0.08s`) to eliminate clicks or trailing dead air:
- `start = max(0, start - pad)`
- `end = min(original_duration, end + pad)`
Then re-merge to handle overlaps introduced by padding.

### 5) Convert removed segments → kept segments
Compute complement intervals (kept content) from `[0, original_duration]` minus removed segments.
- If nothing is removed: keep is `[0, original_duration]`.
- Ensure kept segments are non-empty (`end - start > 0.01`).

### 6) Render compressed video
Reliable approach (re-encode once) using `filter_complex` trim+concat.

Pseudo-structure:
- For each keep segment `k`:
  - video: `trim=start=...:end=...,setpts=PTS-STARTPTS`
  - audio: `atrim=start=...:end=...,asetpts=PTS-STARTPTS`
- Then `concat=n=<num_segments>:v=1:a=1`

Example command template:
```bash
ffmpeg -y -i data/input_video.mp4 \
  -filter_complex "
    [0:v]trim=start=K0S:end=K0E,setpts=PTS-STARTPTS[v0];
    [0:a]atrim=start=K0S:end=K0E,asetpts=PTS-STARTPTS[a0];
    [0:v]trim=start=K1S:end=K1E,setpts=PTS-STARTPTS[v1];
    [0:a]atrim=start=K1S:end=K1E,asetpts=PTS-STARTPTS[a1];
    [v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]
  " \
  -map "[v]" -map "[a]" \
  -c:v libx264 -preset veryfast -crf 23 \
  -c:a aac -b:a 128k \
  compressed_video.mp4
```

If there are many segments, generate the filter graph programmatically.

### 7) Compute report fields (must be consistent)
- `compressed_duration_seconds`: probe output video duration.
- `removed_duration_seconds`: sum of removed segment durations (after merge/padding/clamp).
- `compression_percentage`: `removed / original * 100`.

Consistency checks:
- `abs(original - (compressed + removed)) <= 0.1` (tolerance accounts for encoding and trim rounding).
- Every segment:
  - `0 <= start < end <= original`
  - `duration == end - start` (within 1e-3)

### 8) Write `compression_report.json`
Exact format:
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
If no segments removed, use `"segments_removed": []` and durations set accordingly.

---

## Practical parameter defaults
- Silence detection:
  - `noise=-35dB`, `d=0.3`
- Pause removal threshold: `>= 2.0s`
- Merge gap: `<= 0.3s`
- Padding: `0.08–0.15s`

---

## Common failure modes & fixes
1. **Segments shifted vs actual silence** (especially with custom smoothing):
   - Fix index→time mapping to include hop length and smoothing center offset.
2. **Over-removal harms teaching**:
   - Raise pause threshold (e.g., 2.5s) or reduce padding.
3. **Report math inconsistent**:
   - Always compute removed from final merged list; always probe durations from files.
4. **Negative or overlapping segments**:
   - Clamp, then merge, then filter.

---

## Deliverables checklist
- [ ] `compressed_video.mp4` exists and is playable.
- [ ] `compression_report.json` matches schema.
- [ ] Segment times are valid and ordered.
- [ ] `original ≈ compressed + removed` within tolerance.
