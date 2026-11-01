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
- `--threshold-ratio`: A second is marked low-energy when `energy < local_avg × threshold_ratio` (default: 0.5). Higher values (closer to 1.0) are more permissive/sensitive and flag more pauses; lower values are stricter and flag fewer pauses.
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



Segments use half-open time ranges `[start, end)` in seconds relative to the original input timeline. For example, `{"start": 610, "end": 613}` covers seconds 610, 611, and 612 with duration 3 seconds.
```

## How It Works

1. Load pre-computed energy data
2. Calculate local average using sliding window
3. Mark seconds where `energy < local_avg × threshold_ratio`; increasing `threshold_ratio` causes more seconds to satisfy this condition
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
| `threshold_ratio` | Stricter detection, fewer pauses flagged | More permissive/sensitive, more pauses flagged |
| `min_duration` | Shorter pauses | Longer pauses only |
| `window_size` | Local context | Broader context |



Examples:
- `threshold_ratio=0.3`: only very quiet dips relative to nearby audio are detected
- `threshold_ratio=0.7`: moderate drops below the local average are also detected, producing more pause segments
- Smaller `window_size` reacts quickly to short-term volume changes; larger values smooth over longer sections and reduce sensitivity to brief dips
- `min_duration` is applied after consecutive low-energy seconds are grouped into segments, so increasing it removes short pauses even if they pass the threshold test

## Notes

- Requires energy data from energy-calculator skill
- Use --start-time to skip detected opening
- Local threshold adapts to varying speaker volume
- Preserve pauses whose duration equals `--min-duration`; the threshold is inclusive
