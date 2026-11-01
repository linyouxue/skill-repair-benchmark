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
- `--threshold-ratio`: Low-energy cutoff as a fraction of the **local average** (default: 0.5). A second is marked “pause/low energy” when `energy < local_avg × threshold_ratio`. **Higher values** mark more seconds as pauses (more aggressive removal). **Lower values** are stricter and mark fewer pauses.
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



### Practical guidance (lecture videos)

- Start with `--threshold-ratio 0.5`.
- Typical useful range: **~0.35–0.7**.
  - If you are **missing** obvious pauses/board-writing silences, **increase** the ratio (e.g., 0.55 → 0.65).
  - If you are **removing quiet teaching** (soft voice, mic far away), **decrease** the ratio (e.g., 0.5 → 0.4).
- Caution: when speaker loudness changes a lot, the local average will track the change; prefer small ratio adjustments and consider increasing `--window-size` for smoother context if you see oscillation.

| Parameter | Lower Value | Higher Value |
|-----------|-------------|--------------|
| `threshold_ratio` | Stricter (fewer pauses detected) | More aggressive (more pauses detected) |
| `min_duration` | Shorter pauses | Longer pauses only |
| `window_size` | Local context | Broader context |

## Notes

- Requires energy data from energy-calculator skill
- Use --start-time to skip detected opening
- Local threshold adapts to varying speaker volume
- Preserve pauses whose duration equals `--min-duration`; the threshold is inclusive
