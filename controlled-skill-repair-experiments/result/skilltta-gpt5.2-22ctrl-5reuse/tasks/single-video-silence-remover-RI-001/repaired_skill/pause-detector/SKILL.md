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
- `--start-time`: Start analyzing from this time **in seconds** (default: 0)
- `--threshold-ratio`: Ratio of local average for low energy (default: 0.5)
- `--min-duration`: Minimum pause duration **in seconds** (default: 2)
- `--window-size`: Local average window size **in seconds** (default: 30)

### Output Format

```json
{
  "method": "local_dynamic_threshold",
  "segments": [
    {"start": 610.0, "end": 613.0, "duration": 3.0},
    {"start": 720.0, "end": 724.0, "duration": 4.0}
  ],
  "total_segments": 11,
  "total_duration_seconds": 28.0,
  "parameters": {
    "threshold_ratio": 0.5,
    "window_size": 30,
    "min_duration": 2,
    "start_time": 221
  }
}
```

## How It Works

1. Load pre-computed energy data
2. Read `window_seconds` from `energies.json`
3. Convert seconds-based parameters to energy-frame counts internally:
   - `start_idx ≈ start_time / window_seconds`
   - `min_frames ≈ min_duration / window_seconds`
   - `window_frames ≈ window_size / window_seconds`
4. Calculate local average using a sliding window over energy frames
5. Mark frames where `energy < local_avg × threshold_ratio`
6. Group consecutive low-energy frames into segments
7. Filter segments by minimum duration
8. Emit `start/end/duration` in **seconds** (numbers), regardless of the underlying energy window size

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
```

## Parameters Tuning

| Parameter | Lower Value | Higher Value |
|-----------|-------------|--------------|
| `threshold_ratio` | Stricter low-energy test; fewer removals | Looser low-energy test; more removals |
| `min_duration` | Shorter pauses | Longer pauses only |
| `window_size` | Local context | Broader context |

## Notes

- Requires energy data from energy-calculator skill
- Use `--start-time` to skip a detected opening
- Local threshold adapts to varying speaker volume
- Preserve pauses whose duration equals `--min-duration`; the threshold is inclusive
- Run the documented defaults first and tune from observed local energy contrast, not from a target output duration
