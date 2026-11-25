---
name: skilltta-task-guidance
---

# SkillTTA Task Guidance: Video Silence Remover (single-video)

## Goal
Given `data/input_video.mp4`, produce:
- `compressed_video.mp4`: video with (1) unnecessary opening removed, (2) long pauses (typically >2s) removed, while preserving teaching content.
- `compression_report.json`: consistent segment accounting.

This guidance focuses on three common failure points:
1) **Smoothing window ↔ timestamp alignment** (silence detector)
2) **Segment merge convention** (combiner)
3) **`threshold_ratio` meaning and tuning** (pause detector)

It also borrows robust patterns: validate inputs early, handle empty/no-op cases cleanly, and ensure output math consistency.

---

## 0) Contracts and invariants (must hold)

### Timebase convention (pick one and stick to it)
Use **seconds** everywhere, floating-point.

### Interval convention
Use **half-open intervals**: `[start, end)`.
- Duration = `end - start`
- Two segments `A=[a0,a1)` and `B=[b0,b1)` overlap if `b0 < a1 && a0 < b1`.
- Two segments are mergeable/adjacent if `b0 <= a1 + eps`.

Set `eps = 1e-3` (or 1 frame duration) to absorb rounding.

### Validity constraints
Before writing outputs, assert:
- All removed segments are sorted by `start`.
- `0 <= start < end <= original_duration + eps`.
- No overlaps after merging.
- `removed_duration_seconds ≈ sum(end-start)`.
- `original_duration_seconds ≈ compressed_duration_seconds + removed_duration_seconds` within a small tolerance (e.g., 0.1s).

If nothing is removed, still output a valid `compression_report.json` with an empty `segments_removed`.

---

## 1) Detecting silence: smoothing window ↔ timestamps

### The core pitfall
If you compute a smoothed energy curve over frames/windows, the **timestamp you associate with each smoothed value must match the window’s temporal support**. Misalignment can shift detected start/end times, causing:
- cutting into speech
- missing pauses
- off-by-half-window errors

### Recommended approach
Let audio be processed in fixed hops (frames) of `hop_sec`.
- Frame index `i` corresponds to time `t_i = i * hop_sec` (frame start)

If you smooth with a window length `W` frames:
- If you use a **centered moving average**, smoothed value at index `i` represents time centered at `t_i`, but uses samples from `[i-W/2, i+W/2]`.
  - This implies the *true* support is shifted; boundaries should be adjusted by ~`(W/2)*hop_sec`.
- If you use a **causal moving average** (uses past W), smoothed value at index `i` represents time near the **end** of the window.

### Practical, low-risk rule
Prefer **centered smoothing**, and when converting silent regions back to timestamps:
- Compute silence runs on the smoothed boolean mask.
- Convert run indices `[i0, i1]` to times using:
  - `start = max(0, (i0 - W/2) * hop_sec)`
  - `end   = min(duration, (i1 + 1 + W/2) * hop_sec)`

This “pads” boundaries so you don’t cut speech due to smoothing delay.

### Guard rails
- Ensure `hop_sec` is derived from actual processing (sample_rate, hop_length).
- If you downsample audio or use ffmpeg filters, compute times from the final hop.
- Clamp times to `[0, duration]`.

---

## 2) Pause detection and `threshold_ratio`

### What `threshold_ratio` should mean (make it explicit)
A robust interpretation is relative to a noise/typical level:
- Compute a baseline energy statistic: e.g., `median_energy` (or a low percentile like p20).
- Define silence when `energy < threshold_ratio * median_energy`.

This is usually safer than a fixed absolute dB threshold across different recordings.

### Tuning guidance
- If the detector marks too much as silence (cuts speech): **lower** `threshold_ratio` (stricter), e.g. from `0.6 → 0.4`.
- If it misses pauses: **increase** `threshold_ratio`, e.g. `0.4 → 0.6`.

Also enforce minimum durations:
- `min_silence_len_sec`: typically `2.0` (per task).
- Optional: add a small `speech_padding_sec` (e.g., 0.1–0.2s) to avoid clipping consonants:
  - When removing `[s,e)`, actually remove `[s+pad_left, e-pad_right)` or equivalently keep speech with padding.

### Edge-case handling
If baseline energy is near zero (very quiet track), fall back to:
- use a percentile-based baseline with a floor (epsilon)
- or use ffmpeg `silencedetect` as a secondary check.

---

## 3) Segment combining: merge convention and correctness

### The core pitfall
Different modules may disagree whether intervals are inclusive, half-open, or whether `end` is the last included frame. This leads to:
- tiny gaps/overlaps
- negative durations after rounding
- `ffmpeg` concat errors

### Canonical merge algorithm (half-open)
Given segments sorted by start:
1. Initialize `merged=[]`.
2. For each seg `(s,e)`:
   - Skip if `e - s < min_keep` (invalid).
   - If merged empty: append.
   - Else if `s <= merged[-1].end + eps`: merge by `merged[-1].end = max(merged[-1].end, e)`.
   - Else append.

### Post-merge normalization
- Round times to 3 decimals (ms) *after* merging.
- Ensure monotonically increasing.
- Clamp to duration.

---

## 4) Opening removal heuristic (keep it simple and safe)

A common opening is static/noise with little or no teaching.
Combine signals:
- Audio: long initial silence/noise-only region.
- Visual: low motion (optional if fast).

Simple heuristic:
- If the first detected silence/pause starts at `0.0` and lasts `>= opening_min_sec` (e.g., 1–3s), mark it removable.
- Otherwise, don’t force opening removal beyond what silence detection yields.

If you do visual checks, keep them lightweight (sample 1 fps, compute frame differences).

---

## 5) Output generation workflow (reliable pattern)

1. **Probe duration** with ffprobe.
2. **Detect candidate silent segments** (audio-based), producing `[start,end)` seconds.
3. **Filter** to long pauses: `duration >= 2.0s`.
4. **Merge** segments with the canonical rule.
5. **Compute keep segments** as complement of removed segments over `[0, duration)`.
6. **Render compressed video**:
   - Use ffmpeg concat demuxer or filter_complex with `trim/atrim` + `concat`.
7. **Write JSON report** and validate invariants.

No-op path:
- If `segments_removed` is empty, copy input to `compressed_video.mp4` and output a report with zero removed duration.

---

## 6) Reporting math (must be consistent)

Compute:
- `original_duration_seconds = duration`
- `removed_duration_seconds = sum(end-start)`
- `compressed_duration_seconds = duration - removed_duration_seconds`
- `compression_percentage = removed_duration_seconds / original_duration_seconds * 100`

After encoding, optionally re-probe `compressed_video.mp4` and use the probed duration for `compressed_duration_seconds`, then recompute `removed_duration_seconds ≈ original - compressed` and warn/adjust if mismatch is small (due to keyframes/timebase).

---

## 7) Defensive checks (transferable robust patterns)

Adopt these patterns systematically:
- **Validate inputs**: file exists, duration > 0.
- **Handle empty cases**: if no silence found, still create valid outputs.
- **Avoid in-place mutation pitfalls**: when transforming segment lists, create new lists for each stage (raw → filtered → merged → normalized).
- **Fail fast with clear errors**: if any segment has `end <= start`, log and drop or fix; don’t pass invalid segments to ffmpeg.

---

## Minimal checklist before finishing
- [ ] `compressed_video.mp4` exists and is playable.
- [ ] `compression_report.json` matches schema exactly.
- [ ] All segments within `[0, original_duration]`.
- [ ] `original ≈ compressed + removed` within tolerance.
- [ ] Removed segments plausibly include initial opening (if silent/static) and pauses >2s.
