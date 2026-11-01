---
name: skilltta-task-guidance
description: Temporary guidance for the Video Silence Remover task — focuses on correct audio-based silence detection, timestamp alignment with smoothing windows, and producing a valid compression_report.json plus compressed_video.mp4.
---

# Task Guidance: Video Silence Remover

## Goal
Produce two deliverables in the workspace:
1. `compressed_video.mp4` — input video with opening + long silences (>2s) removed.
2. `compression_report.json` — metadata following the exact schema in the prompt.

## Known Problem Area (from location hint)
The failing region is around the smoothing-window ↔ timestamp mapping in:
- `silence-detector/SKILL.md`
- `silence-detector/scripts/detect_silence.py`
- `video-processor/SKILL.md` (how it calls the detector)

Typical bugs to look for and fix:
- A rolling/moving-average smoothing of RMS energy is applied, but the resulting silence start/end indices are **not shifted back** to compensate for the window offset. If window size = `W` samples (or frames), the smoothed value at index `i` represents samples `[i-W/2, i+W/2]`. Index-to-time must use `t = (i - W/2) * hop / sr`, otherwise every reported segment is late/early by `W/(2*sr)` seconds.
- Using `np.convolve(..., mode='same')` vs `'valid'` changes the index base; make sure the time axis you build matches the mode you chose.
- Hop length / frame length confusion: time per index must be `hop_length / sample_rate`, not `frame_length / sample_rate`.
- The video-processor skill may pass raw frame indices to ffmpeg instead of seconds, or may double-apply the window compensation.

Fix the detector so that returned `(start, end)` are in **seconds, aligned to the original audio timeline**, independent of smoothing window size. Add a unit sanity check: a known-silent clip at `t=5.0s` should be reported starting at ~5.0s regardless of `W`.

## Recommended Pipeline
1. **Probe duration** with `ffprobe` to get `original_duration_seconds`.
2. **Extract audio** to mono 16kHz WAV via `ffmpeg -i input.mp4 -ac 1 -ar 16000 -vn audio.wav`.
3. **Compute RMS** with librosa (`frame_length=2048, hop_length=512`) or raw numpy.
4. **Smooth** RMS (e.g., moving average window ~0.3s). Convert to dB.
5. **Threshold** at e.g. `max_db - 30` (or absolute `-40 dB`). Mark frames below as silent.
6. **Group** consecutive silent frames into intervals.
7. **Convert indices → seconds correctly**: `t = idx * hop_length / sr`. Do NOT add any window-size offset if you used `mode='same'`; verify with a synthetic test.
8. **Opening removal**: treat the first non-silent region's start as the opening cutoff; if the first `>N` seconds are silent/static, remove `[0, first_speech_start]`.
9. **Filter** silence segments: keep only those with `duration > 2.0` seconds.
10. **Cut and concatenate** kept segments with ffmpeg. Prefer the `select`/`aselect` filter with `setpts`/`asetpts` for a single-pass cut:
   ```
   ffmpeg -i input.mp4 -vf "select='<expr>',setpts=N/FRAME_RATE/TB" \
          -af "aselect='<expr>',asetpts=N/SR/TB" compressed_video.mp4
   ```
   where `<expr>` is a disjunction of `between(t,start,end)` for KEPT intervals.
11. **Write report** with consistent math: `original ≈ compressed + removed` (allow <0.5s tolerance).

## compression_report.json schema (must match exactly)
```json
{
  "original_duration_seconds": <float>,
  "compressed_duration_seconds": <float>,
  "removed_duration_seconds": <float>,
  "compression_percentage": <float>,  // (removed/original)*100
  "segments_removed": [
    {"start": <float>, "end": <float>, "duration": <float>}
  ]
}
```

## Patterns Borrowed from Prior Working Solutions
- **Explicit schema construction** (as in the JSON-writing example): build the dict in Python, dump with `json.dump`, and save under `os.getcwd()` to guarantee the file lands in the workspace.
- **Guard clauses first** (as in the DataFrame analyzer): before processing, verify `input_video.mp4` exists, audio stream exists, and ffmpeg/ffprobe are callable. Fail fast with a clear message.
- **Preprocessing-before-vectorization pattern** (as in the CountVectorizer example): clean/normalize the raw signal (strip DC, drop near-zero frames) before thresholding, analogous to dropping empty sentences before vectorizing. This prevents degenerate silence detections.

## Sanity Checks Before Returning
- Sum of `segments_removed` durations ≈ `removed_duration_seconds` (±0.1s).
- `compressed_duration_seconds` ≈ ffprobe duration of the output file (±0.5s).
- No segment overlaps; all are in `[0, original_duration]`; all have `duration > 0`.
- Compression percentage is reasonable (typically 5–40% for a 10-min teaching video).
- Teaching content audible on spot-check at a few timestamps.

## Minimal Smoothing/Timestamp Reference Snippet
```python
import numpy as np, librosa
y, sr = librosa.load('audio.wav', sr=16000, mono=True)
hop = 512
rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=hop)[0]
# times for each RMS frame — THIS is the canonical mapping
times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop)
# smoothing: 'same' keeps len == len(rms), so times[] still aligns 1:1
W = max(1, int(0.3 * sr / hop))
rms_s = np.convolve(rms, np.ones(W)/W, mode='same')
db = 20*np.log10(rms_s + 1e-9)
thr = db.max() - 30
silent = db < thr
# derive intervals from `silent` using `times` — never add extra W/2 offset
```
Use `times[i]` directly; do not re-apply any window compensation afterwards.
