---
name: pause-detector
description: Detect pauses and silence in audio using local dynamic thresholds. Use when you need to find natural pauses in lectures, board-writing silences, or breaks between sections. Uses local context comparison to avoid false positives from volume variation.
---

# Pause Detector

Detects pauses and low-energy segments using local dynamic thresholds on pre-computed energy data. Unlike global threshold methods, this compares energy to surrounding context, avoiding false positives when speaker volume varies.

## Use Cases

- Detecting natural pauses in lectures
- Finding board-writing silences
- Identifying breaks between sections

## Usage

```bash
python3 /root/.claude/skills/pause-detector/scripts/detect_pauses.py \
    --energies /path/to/energies.json \
    --output /path/to/pauses.json
```

### Parameters

- `--energies`: Path to energy JSON file (from energy-calculator)
- `--output`: Path to output JSON file
- `--start-time`: Start analyzing from this second (default: 0)
- `--threshold-ratio`: Ratio of local average for low energy (default: 0.5)
- `--min-duration`: Minimum pause duration in seconds (default: 2)
- `--window-size`: Local average window size (default: 30)

### Output Format

```json
{
  "method": "local_dynamic_threshold",
  "segments": [
    {"start": 610, "end": 613, "duration": 3},
    {"start": 720, "end": 724, "duration": 4}
  ],
  "total_segments": 11,
  "total_duration_seconds": 28,
  "parameters": {
    "threshold_ratio": 0.5,
    "window_size": 30,
    "min_duration": 2
  }
}
```

## How It Works

1. Load pre-computed energy data
2. Calculate local average using sliding window
3. Mark seconds where energy < local_avg × threshold_ratio
4. Group consecutive low-energy seconds into segments
5. Filter segments by minimum duration

## Dependencies

- Python 3.11+
- numpy
- scipy

## Example

```bash
# Detect pauses after opening (start at 221s)
python3 /root/.claude/skills/pause-detector/scripts/detect_pauses.py \
    --energies energies.json \
    --start-time 221 \
    --output pauses.json

# Result: Found 11 pauses totaling 28 seconds
```

## Parameters Tuning

| Parameter | Lower Value | Higher Value |
|-----------|-------------|--------------|
| `threshold_ratio` | More aggressive | More conservative |
| `min_duration` | Shorter pauses | Longer pauses only |
| `window_size` | Local context | Broader context |



## Lecture Video Preset + Practical Tuning Loop (recommended for video-silence-remover)

Lecture/teaching audio often has variable volume, quiet speech, and short pauses (2–5s). Use this loop to avoid **missed pauses (low recall)** and **borderline-speech false positives (low precision)**.

### Starting preset (good first try)

```bash
python3 /root/.claude/skills/pause-detector/scripts/detect_pauses.py \
  --energies energies.json \
  --start-time 0 \
  --threshold-ratio 0.45 \
  --window-size 45 \
  --min-duration 2 \
  --output pauses.json
```

### Parameter sweep ranges (what to try next)

Run a small sweep and inspect outputs; pick the setting that best matches your target segments.

- `--threshold-ratio`: **0.35–0.60**
  - Lower (0.35–0.45) = higher recall (detect more pauses) but risks cutting quiet speech.
  - Higher (0.50–0.60) = higher precision (safer) but can miss 2–5s pauses.
- `--window-size`: **20–60**
  - Smaller = reacts faster to local changes; can be noisy.
  - Larger = more stable across long lectures with drifting loudness.
- `--min-duration`: **>= 2** (commonly 2–4)
  - 2 = catches typical “thinking/board-writing” pauses.
  - 3–4 = safer if you see many false positives.

Suggested quick grid (keep it small):
- threshold_ratio ∈ {0.40, 0.45, 0.50, 0.55}
- window_size ∈ {30, 45, 60}
- min_duration ∈ {2, 3}

### How to diagnose and adjust

Use these symptoms to decide what to change:

**A) Missing obvious pauses (under-detection / low recall)**
- Decrease `--threshold-ratio` (e.g., 0.50 → 0.45 → 0.40)
- Increase `--window-size` if volume drifts over time (e.g., 30 → 45/60)
- Keep `--min-duration` at 2 (don’t raise it while chasing recall)

**B) Cutting into quiet speech (over-detection / low precision)**
- Increase `--threshold-ratio` (e.g., 0.45 → 0.50 → 0.55)
- Increase `--min-duration` (2 → 3 or 4) to drop short borderline segments
- Consider reducing `--window-size` if the “local average” is too high due to nearby loud peaks

### Quick inspection helpers

Show longest detected pauses:
```bash
jq '.segments | sort_by(-.duration)[:15]' pauses.json
```

See count and total removed time:
```bash
jq '{n:(.segments|length), total:([.segments[].duration]|add)}' pauses.json
```
## Notes

- Requires energy data from energy-calculator skill
- Use --start-time to skip detected opening
- Local threshold adapts to varying speaker volume


## Post-processing for Better IoU / Cleaner Cuts (merge + pad + drop)

For evaluator-style matching (IoU-based) and smoother video edits, post-process detected pauses before cutting.

### 1) Merge pauses separated by small gaps
If two pauses are separated by a tiny gap (often a breath/noise spike), merge them to avoid rapid jump-cuts.

- Merge gap threshold: **<= 0.5–1.0s**

Rule: if `next.start - prev.end <= gap`, replace with `{start: prev.start, end: next.end}`.

### 2) Optional padding to improve alignment
Detectors often start/end slightly inside the true pause. Padding helps IoU.

- Pad each segment by **0.2–0.5s** on both sides.
- Cap padding so you do not clip speech:
  - Do not pad across a non-silent region longer than your merge gap.
  - Clamp to `[0, media_duration]`.

Practical default: **pad=0.3s**, **cap=0.5s**.

### 3) Drop micro / low-confidence segments
To reduce false positives:
- Drop segments shorter than your target (already controlled by `--min-duration`).
- Also consider dropping segments very close to the threshold (if you track confidence externally) or segments that appear as single isolated dips.

### 4) Opening interaction (avoid double-removal)
If you also remove an opening segment (common in this benchmark), handle overlaps explicitly:

- If a detected pause overlaps the opening removal interval, either:
  - **clip** it to start at `opening_end`, or
  - **discard** it if it lies fully inside the opening.

This prevents double-counting removed time and avoids cutting away the first teaching words right after the opening.
