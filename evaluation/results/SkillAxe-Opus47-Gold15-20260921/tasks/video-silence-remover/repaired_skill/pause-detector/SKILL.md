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

### Recommended settings for precision

Default parameters can over-detect short low-energy dips. When the task calls for pauses strictly longer than 2 seconds (e.g., `> 2 sec`), prefer:

- `--min-duration 3` to exclude borderline 2-second segments that are frequently false positives (short breaths, sentence gaps, transient volume dips).
- `--threshold-ratio 0.4` (more conservative) if the speaker has variable volume and mid-teaching dips are being flagged.

Exactly-2s segments returned by default settings should be scrutinized — many are natural inter-word gaps rather than true teaching pauses.

## Post-processing: merge near-adjacent segments

Raw detector output can split a single real pause into multiple short segments when a transient noise (breath, cough, click) briefly crosses the threshold. **Before feeding segments downstream, merge segments whose gap is small.**

Recommended merge rule after loading `segments` from this skill's output:

```python
import json

def merge_close_segments(segments, max_gap=2):
    if not segments:
        return []
    segments = sorted(segments, key=lambda s: s["start"])
    merged = [dict(segments[0])]
    for seg in segments[1:]:
        if seg["start"] - merged[-1]["end"] <= max_gap:
            merged[-1]["end"] = max(merged[-1]["end"], seg["end"])
            merged[-1]["duration"] = merged[-1]["end"] - merged[-1]["start"]
        else:
            merged.append(dict(seg))
    return merged

data = json.load(open("pauses.json"))
data["segments"] = merge_close_segments(data["segments"], max_gap=2)
data["total_segments"] = len(data["segments"])
data["total_duration_seconds"] = sum(s["duration"] for s in data["segments"])
json.dump(data, open("pauses.json", "w"), indent=2)
```

A gap of ≤ 2 seconds between candidate pauses almost always indicates a single real pause that was split; merging improves segment-detection precision without hurting recall.

## Notes

- Requires energy data from energy-calculator skill
- Use --start-time to skip detected opening
- Local threshold adapts to varying speaker volume
- Always apply the near-adjacent merge step (gap ≤ 2s) before combining with other segment sources; unmerged fragments hurt precision on IoU-based evaluations.
- If a task specifies pauses "> N seconds", set `--min-duration` to at least `N + 1` (strict inequality) after merging, since a segment of exactly N seconds does not satisfy `> N`.
