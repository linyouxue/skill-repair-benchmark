---
name: pause-detector
description: Detect pauses and silence in audio using local dynamic thresholds. Use when you need to find natural pauses in lectures, board-writing silences, or breaks between sections. Uses local median-based context comparison to stay robust during long pauses.
---

# Pause Detector

Detects pauses and low-energy segments using a **local median** dynamic
threshold on pre-computed energy data. Unlike mean-based local methods,
the median reference is not pulled down by the pause itself, so a long
pause stays below the threshold for its entire duration.

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
- `--start-time`: Start analyzing from this second (default: 0). Typically
  set to the opening end reported by `silence-detector`.
- `--threshold-ratio`: Fraction of the **local median** RMS below which a
  second is counted as silent (default: `0.3`).
- `--min-duration`: Minimum pause duration in seconds, inclusive
  (default: `2`). Pauses of exactly `min_duration` seconds are kept.
- `--window-size`: Width in seconds of the sliding window used for the
  local median reference (default: `60`).

### Threshold semantics

`is_silent[i] = energy[i] < threshold_ratio * median_in_window(i)`

- The reference is the **median** inside a window of `window_size`
  seconds centered on `i`. A long pause does not drag the median down,
  so the condition stays true for the full pause.
- Lower `threshold_ratio` ⇒ more conservative (only very quiet frames
  qualify). Higher ⇒ more aggressive.
- `silence-detector`'s `--threshold-multiplier` and this detector's
  `--threshold-ratio` are **not interchangeable** numerically:
  silence-detector multiplies a *global* baseline, pause-detector takes a
  fraction of a *local* reference. Treat them as separate knobs.

### Output Format

```json
{
  "method": "local_dynamic_threshold_median",
  "segments": [
    {"start": 610, "end": 613, "duration": 3},
    {"start": 720, "end": 724, "duration": 4}
  ],
  "total_segments": 11,
  "total_duration_seconds": 28,
  "parameters": {
    "threshold_ratio": 0.3,
    "window_size": 60,
    "min_duration": 2,
    "start_time": 221,
    "local_reference": "median"
  }
}
```

## How It Works

1. Load pre-computed per-second energies.
2. Compute a local **median** reference with `scipy.ndimage.median_filter`
   over a window of `window_size` seconds.
3. Mark seconds where `energy < threshold_ratio * local_median`.
4. Group consecutive low-energy seconds into segments.
5. Keep segments whose duration is `>= min_duration` (inclusive).

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
    --threshold-ratio 0.3 \
    --window-size 60 \
    --output pauses.json
```

## Parameters Tuning

| Parameter | Lower Value | Higher Value |
|-----------|-------------|--------------|
| `threshold_ratio` | More conservative (only very quiet frames) | More aggressive |
| `min_duration` | Shorter pauses | Longer pauses only |
| `window_size` | More locally-adaptive | Broader, more stable reference |

## Notes

- Requires energy data from energy-calculator skill.
- Use `--start-time` to skip the detected opening from `silence-detector`.
- Local median reference adapts to varying speaker volume while remaining
  robust during long pauses.
- Pauses of exactly `min_duration` seconds are preserved; the comparison
  is inclusive (`>=`).
