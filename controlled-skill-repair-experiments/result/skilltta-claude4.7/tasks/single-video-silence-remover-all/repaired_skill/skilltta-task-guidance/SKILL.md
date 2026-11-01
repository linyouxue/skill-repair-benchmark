---
name: skilltta-task-guidance
description: Temporary guidance Skill for the Video Silence Remover task. Consolidates lessons about silence detection smoothing windows, segment merging conventions, and threshold ratio semantics across sub-skills, and gives a concrete pipeline to produce compressed_video.mp4 and compression_report.json.
---

# Video Silence Remover — Task Guidance Skill

## Goal
Given `data/input_video.mp4` (~10 min teaching video), produce:
1. `compressed_video.mp4` — video with the unnecessary opening and long silent pauses (>2s) removed.
2. `compression_report.json` — report matching the exact schema in the task prompt.

## High-Level Pipeline
1. Probe original duration with `ffprobe`.
2. Extract mono 16kHz PCM audio with `ffmpeg -ac 1 -ar 16000 -vn -f wav`.
3. Detect silence from audio RMS envelope.
4. Detect the opening (long low-energy / static region at the start) and force-remove it even if just under the silence threshold.
5. Merge nearby silence intervals and clamp them to [0, duration].
6. Build the complementary keep-list, cut and concat with ffmpeg.
7. Write JSON report with consistent math.

## Known Pitfalls (addressed by location hints)

### 1. Smoothing window ↔ timestamp alignment (silence-detector / detect_silence.py)
- When computing RMS over frames of size `hop` samples and then applying a moving-average smoothing window of length `W` frames, the smoothed value at index `i` corresponds to the *center* of the window, not the left edge.
- Convert indices to seconds using `t = (i + W/2) * hop / sr` for center-aligned smoothing, or shift back by `W*hop/(2*sr)` when reporting silence `start`/`end`. Otherwise reported silence boundaries drift by half a window and cuts land inside speech.
- Document in SKILL.md that `detect_silence.py` outputs *center-aligned* timestamps so downstream consumers (video-processor) must not re-shift.

### 2. Segment merge convention (segment-combiner)
- Intervals are half-open `[start, end)` in seconds.
- Merge rule: sort by `start`; merge when `next.start - current.end <= gap_tolerance` (default 0.3s) to avoid micro-fragments.
- After merging, drop any segment with `duration < min_silence_duration` (default 2.0s) **except** the opening segment, which is always kept if it starts at ~0.0.
- Clamp all segments to `[0, total_duration]` and ensure no overlap before passing to ffmpeg.
- video-processor must call the combiner *before* building keep-ranges, and must assert `sum(removed) + compressed_duration ≈ original_duration` within 0.2s.

### 3. `threshold_ratio` semantics (pause-detector / silence-detector / video-processor)
- `threshold_ratio` is a fraction of the **median** (not max) RMS of the whole audio. A frame is silent if `rms[i] < threshold_ratio * median_rms`.
- Recommended default: `0.3`. For noisy openings (static with hiss), using `max` as reference makes the threshold too high and misses the opening; using `median` keeps it robust.
- silence-detector and pause-detector must agree on this definition; video-processor should expose it as a single CLI flag and pass the same value to both.

## Reusable Patterns from Retrieved Examples
- **Guard-clause early returns** (BigCodeBench/175): before processing, verify `input_video.mp4` exists and has an audio stream; otherwise write a minimal valid JSON with zero removals.
- **Clean tokenization / filtering of empties** (BigCodeBench/54): when splitting the timeline into keep-segments between silences, drop zero-length segments (`end - start < 0.05s`) just like dropping empty sentences.
- **Single-dict JSON serialization with os.path** (BigCodeBench/265): assemble the full report dict first, then `json.dump` once; always write to `os.path.join(os.getcwd(), 'compression_report.json')`.

## Concrete Recipe

```bash
# 1. duration
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 data/input_video.mp4)

# 2. audio
ffmpeg -y -i data/input_video.mp4 -ac 1 -ar 16000 -vn audio.wav
```

```python
# 3+4+5. detect silences (center-aligned, median-based threshold)
import numpy as np, soundfile as sf, json, subprocess, os
y, sr = sf.read('audio.wav')
hop = 1024
frames = [y[i:i+hop] for i in range(0, len(y)-hop, hop)]
rms = np.array([np.sqrt(np.mean(f*f)+1e-12) for f in frames])
W = 15                               # smoothing window (frames)
kernel = np.ones(W)/W
sm = np.convolve(rms, kernel, mode='same')  # 'same' => center-aligned
thr = 0.3 * np.median(sm)
silent = sm < thr

# frame index -> seconds (center of frame)
def t(i): return (i + 0.5) * hop / sr

segs = []
i = 0
while i < len(silent):
    if silent[i]:
        j = i
        while j < len(silent) and silent[j]:
            j += 1
        segs.append([t(i), t(j)])
        i = j
    else:
        i += 1

# merge close, drop short (except opening)
MERGE_GAP, MIN_DUR = 0.3, 2.0
merged = []
for s,e in segs:
    if merged and s - merged[-1][1] <= MERGE_GAP:
        merged[-1][1] = e
    else:
        merged.append([s,e])

dur = float(subprocess.check_output(
    ['ffprobe','-v','error','-show_entries','format=duration',
     '-of','csv=p=0','data/input_video.mp4']).strip())

final = []
for idx,(s,e) in enumerate(merged):
    s = max(0.0, s); e = min(dur, e)
    is_opening = (idx == 0 and s < 1.0)
    if (e - s) >= MIN_DUR or is_opening:
        final.append([s,e])

# 6. build keep ranges and cut
keep = []
cur = 0.0
for s,e in final:
    if s - cur > 0.05:
        keep.append([cur, s])
    cur = e
if dur - cur > 0.05:
    keep.append([cur, dur])

parts = []
for k,(a,b) in enumerate(keep):
    out = f'part_{k:03d}.mp4'
    subprocess.run(['ffmpeg','-y','-ss',f'{a}','-to',f'{b}',
                    '-i','data/input_video.mp4',
                    '-c:v','libx264','-c:a','aac','-preset','veryfast',out],
                   check=True)
    parts.append(out)

with open('concat.txt','w') as f:
    for p in parts: f.write(f"file '{p}'\n")
subprocess.run(['ffmpeg','-y','-f','concat','-safe','0',
                '-i','concat.txt','-c','copy','compressed_video.mp4'], check=True)

# 7. report
compressed = float(subprocess.check_output(
    ['ffprobe','-v','error','-show_entries','format=duration',
     '-of','csv=p=0','compressed_video.mp4']).strip())
removed = sum(e-s for s,e in final)
report = {
    'original_duration_seconds': round(dur,3),
    'compressed_duration_seconds': round(compressed,3),
    'removed_duration_seconds': round(removed,3),
    'compression_percentage': round(removed/dur*100,2),
    'segments_removed': [
        {'start': round(s,3), 'end': round(e,3), 'duration': round(e-s,3)}
        for s,e in final
    ],
}
with open(os.path.join(os.getcwd(),'compression_report.json'),'w') as f:
    json.dump(report, f, indent=2)
```

## Sanity Checks Before Finishing
- `abs(original - (compressed + removed)) < 0.5s`.
- `0 < compression_percentage < 60` (teaching content preserved).
- Every segment: `0 <= start < end <= original_duration` and `duration == end - start`.
- Opening segment removed if the video starts with >1s of static/low-energy audio.
- Both files exist at workspace root: `compressed_video.mp4`, `compression_report.json`.
