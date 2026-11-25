---
name: skilltta-task-guidance
---

# SkillTTA Task Guidance: Video Silence Remover

## Goal
Given `data/input_video.mp4`, produce:
1. `compressed_video.mp4`: video with (a) unnecessary opening removed and (b) long pauses (typically >2s) removed, while preserving teaching content.
2. `compression_report.json`: consistent math and valid, merged removal segments.

This guidance emphasizes **robust validation**, **safe defaults**, **interval merging conventions**, and **math-consistent reporting**.

---

## Robust patterns to reuse (transferable)
### 1) Validate prerequisites and fail safely
Like the passing examples that return an empty plot / minimal output when inputs are insufficient, do similar here:
- If `data/input_video.mp4` missing or unreadable: stop early with a clear error.
- If silence detection yields no removable segments: output should still be valid:
  - `compressed_video.mp4` should be a fast copy (or re-mux) of the original.
  - `compression_report.json` should show `removed_duration_seconds = 0` and an empty `segments_removed`.

### 2) Avoid unintended mutation
When transforming lists of segments, create new lists/copies before editing (mirrors the DataFrame `.copy()` pattern).

### 3) Compute derived metrics explicitly and ensure consistency
As in the JSON-saving example (compute frequency then serialize), here:
- Compute durations from timestamps.
- Ensure:
  - `original_duration_seconds ≈ compressed_duration_seconds + removed_duration_seconds` (allow small tolerance like 0.05–0.2s due to rounding/timebase).
  - `compression_percentage = removed / original * 100` (define and keep consistent).

---

## Recommended approach (fast + accurate): ffmpeg silencedetect + concat
### A) Get original duration
Use `ffprobe`:
- Duration `T` in seconds.

### B) Detect silence intervals (audio-based)
Use ffmpeg filter `silencedetect`:
- Typical parameters:
  - `d=2.0` (minimum silence length to consider removable)
  - `noise=-35dB` to `-30dB` (tune if needed)

Example command:
```bash
ffmpeg -hide_banner -i data/input_video.mp4 -af silencedetect=noise=-35dB:d=2 -f null - 2> silence.log
```
Parse `silence.log` for pairs:
- `silence_start: <t>`
- `silence_end: <t> | silence_duration: <d>`

**Edge cases**:
- If silence starts but never ends (video ends in silence): treat end as `T`.
- If silence end appears without a start: ignore or clamp safely.

### C) Remove unnecessary opening
Commonly the opening is silent/static. Practical rule:
- If there is a silence interval starting at (or extremely near) `0.0` and lasting at least ~1–2s, remove it.
- Optionally, you may extend removal slightly for static intros by:
  - Removing initial silence plus a small extra buffer (e.g., +0.2s) if safe.

Keep this conservative to “keep teaching content as much as possible.”

---

## Interval conventions + segment combiner (critical)
### Interval convention (must be consistent)
Use **half-open** time intervals:
- A removed segment is `[start, end)` in seconds.
- Duration is `end - start`.

### Normalization
Before merging, normalize all candidate segments:
- Clamp: `start = max(0, start)`, `end = min(T, end)`
- Drop invalid: if `end <= start`, skip.

### Merge/Combine rule (align with typical segment-combiner expectations)
Sort by `start`, then merge if:
- Overlapping: `next.start <= cur.end`
- Or nearly contiguous: `next.start - cur.end <= merge_gap`

Use a small `merge_gap` like `0.05`–`0.15` seconds to prevent micro-gaps from creating unnecessary cuts.

Pseudo-code:
```python
segments = sorted(segments, key=lambda x: x[0])
merged = []
for s,e in segments:
    if not merged:
        merged.append([s,e]); continue
    ps,pe = merged[-1]
    if s <= pe + merge_gap:
        merged[-1][1] = max(pe, e)
    else:
        merged.append([s,e])
```

### Optional padding (be conservative)
To avoid clipping words, you can shrink removed segments slightly:
- `start += keep_pad`
- `end   -= keep_pad`
Where `keep_pad` ~ `0.05`–`0.15` seconds.
After padding, revalidate and re-merge.

---

## Build the compressed video
### 1) Convert removed intervals → keep intervals
Given removed merged intervals `R = [r1, r2, ...]`, produce keep segments `K` as the complement within `[0, T)`:
- Start cursor at 0
- For each removed `[s,e)`:
  - If `cursor < s`: keep `[cursor, s)`
  - Set `cursor = e`
- After all, if `cursor < T`: keep `[cursor, T)`

If `K` is empty (everything removed), fall back to keeping at least a minimal segment (e.g., first 1s) or just output original; but usually shouldn’t happen.

### 2) Concatenate keep segments with ffmpeg
Most robust method is using `-filter_complex` with `trim/atrim` and `concat`.
Sketch:
- For each keep segment i:
  - video: `trim=start=...:end=...,setpts=PTS-STARTPTS`
  - audio: `atrim=start=...:end=...,asetpts=PTS-STARTPTS`
- Then concat all: `concat=n=<N>:v=1:a=1`

This avoids re-encoding multiple times; it will do one final encode.

Encoding suggestion:
- Use H.264 + AAC for broad compatibility.

---

## Produce `compression_report.json`
Required structure:
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
- `segments_removed` must be the **merged** removed intervals.
- Each item:
  - `duration = end - start`
  - Numbers should be JSON numbers (not strings).
- Compute:
  - `removed_duration_seconds = sum(duration)`
  - `compressed_duration_seconds = original_duration_seconds - removed_duration_seconds`
  - `compression_percentage = (removed / original) * 100` (0 if original is 0)

Consistency check (recommended):
- If `abs(original - (compressed + removed)) > 0.2`, re-check rounding/clamping.

---

## Practical defaults (good starting point)
- `silencedetect`: `noise=-35dB`, `d=2.0`
- `merge_gap`: `0.1`
- `keep_pad`: `0.08` (optional; if used, apply after detection)

---

## Minimal “no segments found” behavior
If there are no removable segments after normalization/merging:
- Create `compressed_video.mp4` as a fast copy/remux:
  - e.g., `ffmpeg -i input -c copy compressed_video.mp4` (if container/codec allow)
- Write report with empty `segments_removed` and 0 removed duration.

This mirrors the retrieved examples’ pattern of returning a valid object even when the target condition isn’t met.
