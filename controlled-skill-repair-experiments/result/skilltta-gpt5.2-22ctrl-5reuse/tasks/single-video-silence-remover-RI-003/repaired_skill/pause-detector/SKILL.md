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
- `--threshold-ratio`: Ratio of local average for low energy (default: 0.2)
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
    "threshold_ratio": 0.2,
    "window_size": 30,
    "min_duration": 2
  }
}
```

## How It Works

1. Load pre-computed energy data
2. Calculate local average using sliding window
3. Mark seconds where `energy < local_avg × threshold_ratio`
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

# Result: Found pauses totaling N seconds
```

## Parameters Tuning

Important: this detector uses the rule:

- **pause if** `energy < local_avg × threshold_ratio`

So:

- **Higher `threshold_ratio` ⇒ higher cutoff ⇒ more seconds counted as “low energy” ⇒ more aggressive pause removal**
- **Lower `threshold_ratio` ⇒ lower cutoff ⇒ fewer seconds counted as “low energy” ⇒ more conservative**

Recommended starting values for lecture/teaching videos:
- `threshold_ratio`: **0.10–0.25** (start around **0.20**)

Tuning heuristic:
- If it cuts into quiet speech: **decrease** `threshold_ratio`.
- If it misses obvious long pauses: **increase** `threshold_ratio`.

| Parameter | Lower Value | Higher Value |
|-----------|-------------|--------------|
| `threshold_ratio` | More conservative | More aggressive |
| `min_duration` | Shorter pauses | Longer pauses only |
| `window_size` | More local context | Broader context |

## Notes

- Requires energy data from energy-calculator skill
- Use --start-time to skip detected opening
- Local threshold adapts to varying speaker volume
- Preserves pauses whose duration equals `--min-duration` (`>=` in implementation)
