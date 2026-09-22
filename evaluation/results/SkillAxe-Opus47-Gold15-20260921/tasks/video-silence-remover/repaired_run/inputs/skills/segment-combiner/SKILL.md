---
name: segment-combiner
description: Combine multiple segment detection results into a unified list. Use when you need to merge segments from different detectors, prepare removal lists for video processing, or consolidate detection outputs.
---

# Segment Combiner

Combines multiple segment JSON files into a single unified segments file for video processing.

## Use Cases

- Merging segments from multiple detectors
- Consolidating detection results
- Preparing unified input for video-processor

## Usage

```bash
python3 /root/.claude/skills/segment-combiner/scripts/combine_segments.py \
    --segments /path/to/segments1.json /path/to/segments2.json \
    --output /path/to/all_segments.json
```

### Parameters

- `--segments`: One or more segment JSON files to combine
- `--output`: Path to output combined segments JSON

### Input Format

Each input file should have a `segments` array:

```json
{
  "segments": [
    {"start": 0, "end": 120, "duration": 120},
    {"start": 300, "end": 305, "duration": 5}
  ]
}
```

### Output Format

```json
{
  "segments": [
    {"start": 0, "end": 120, "duration": 120},
    {"start": 300, "end": 305, "duration": 5}
  ],
  "total_segments": 2,
  "total_duration_seconds": 125
}
```

## Dependencies

- Python 3.11+

## Example

```bash
# Combine segments from multiple detectors
python3 /root/.claude/skills/segment-combiner/scripts/combine_segments.py \
    --segments initial_silence.json pauses.json \
    --output all_segments.json
```

## Recommended pre-processing

Before combining, sanity-check each input segment list:

1. **Merge near-adjacent segments within each source** (gap ≤ 2 s). Detectors frequently split one real pause into multiple pieces due to transient audio spikes; combining without merging leaves fragmented segments that fail IoU-based precision checks.
2. **Drop segments shorter than the task threshold.** If the task calls for pauses ">N seconds", filter out any segment with `duration <= N` after merging.
3. Verify that no two segments overlap or touch after merging; if the combiner produces adjacent ranges (e.g., `end=231` then `start=232`), merge them too before invoking `video-processor`.

Example cleanup step usable on the combined output:

```python
import json
data = json.load(open("all_segments.json"))
segs = sorted(data["segments"], key=lambda s: s["start"])
merged = []
for s in segs:
    if merged and s["start"] - merged[-1]["end"] <= 2:
        merged[-1]["end"] = max(merged[-1]["end"], s["end"])
        merged[-1]["duration"] = merged[-1]["end"] - merged[-1]["start"]
    else:
        merged.append(dict(s))
data["segments"] = merged
data["total_segments"] = len(merged)
data["total_duration_seconds"] = sum(s["duration"] for s in merged)
json.dump(data, open("all_segments.json", "w"), indent=2)
```

## Notes

- Segments are sorted by start time
- Compatible with video-processor --remove-segments input
- All input files must have `segments` array
- Fragmented or exactly-threshold-length segments are the most common cause of low precision in downstream evaluation; apply the pre-processing step above whenever combining audio-derived pauses.
