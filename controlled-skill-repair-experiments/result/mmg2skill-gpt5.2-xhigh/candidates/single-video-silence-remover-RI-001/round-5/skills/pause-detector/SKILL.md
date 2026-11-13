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
python3 /skills/pause-detector/scripts/detect_pauses.py \
    --energies /path/to/energies.json \
    --output /path/to/pauses.json
```

### Parameters

- `--energies`: Path to energy JSON file (from energy-calculator)
- `--output`: Path to output JSON file
- `--start-time`: Start analyzing from this second (default: 0)
- `--threshold-ratio`: Ratio of local average for low energy (default: 0.5)
- `--min-duration`: Minimum pause duration in seconds (default: 2). Because durations are counted in 1s bins and the filter is `>= min_duration`, use `--min-duration 3` to target pauses “> 2s” and avoid removing borderline 2-second micro-pauses.
- `--window-size`: Local average window size (default: 30)

### Output Format

```json
{
  "method": "local_dynamic_threshold",
  "segments": [
    {"start": 610, "end": 614, "duration": 4},
    {"start": 720, "end": 725, "duration": 5}
  ],
  "total_segments": 2,
  "total_duration_seconds": 9,
  "parameters": {
    "threshold_ratio": 0.5,
    "window_size": 30,
    "min_duration": 3,
    "start_time": 221
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
# Detect pauses after opening (start at 221s) and keep precision high by ignoring 2s micro-pauses
python3 /skills/pause-detector/scripts/detect_pauses.py \
    --energies energies.json \
    --start-time 221 \
    --min-duration 3 \
    --output pauses.json
```

## Parameters Tuning

| Parameter | Lower Value | Higher Value |
|-----------|-------------|--------------|
| `threshold_ratio` | Stricter low-energy test; fewer removals | Looser low-energy test; more removals |
| `min_duration` | Shorter pauses (lower precision) | Longer pauses only (higher precision) |
| `window_size` | Local context | Broader context |

## Notes

- Requires energy data from energy-calculator skill
- Use `--start-time` to skip detected opening
- Local threshold adapts to varying speaker volume
- If you see many pause segments exactly at the minimum duration, increase `--min-duration` (or lower `--threshold-ratio`) to improve precision while keeping longer pauses.
