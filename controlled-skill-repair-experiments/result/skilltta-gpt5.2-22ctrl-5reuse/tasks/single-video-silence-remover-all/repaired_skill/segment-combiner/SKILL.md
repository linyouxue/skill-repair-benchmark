---
name: segment-combiner
description: Combine multiple segment detection results into a unified list. Use when you need to merge segments from different detectors, prepare removal lists for video processing, or consolidate detection outputs.
---

# Segment Combiner

Combines multiple segment JSON files into a single unified segments file for video processing.

## Contract (important)

- **Time unit**: seconds (float)
- **Interval convention**: **half-open** intervals `[start, end)`
- **Duration**: `duration = end - start` (the combiner recomputes duration)
- The combiner **merges overlaps and adjacent segments** to prevent double-counting.

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
- `--duration`: Optional clamp duration in seconds (clamps segments to `[0, duration]`)
- `--eps`: Merge epsilon in seconds (segments are merged when `next.start <= cur.end + eps`)

### Input Format

Each input file should have a `segments` array:

```json
{
  "segments": [
    {"start": 0.0, "end": 120.0, "duration": 120.0},
    {"start": 300.0, "end": 305.0, "duration": 5.0}
  ]
}
```

`duration` is optional in inputs; it is recomputed by the combiner.

### Output Format

```json
{
  "segments": [
    {"start": 0.0, "end": 120.0, "duration": 120.0},
    {"start": 300.0, "end": 305.0, "duration": 5.0}
  ],
  "total_segments": 2,
  "total_duration_seconds": 125.0,
  "parameters": {
    "eps": 0.001,
    "clamp_duration": null
  }
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

## Notes

- Segments are sorted by start time
- Overlapping/adjacent segments are merged
- Compatible with video-processor --remove-segments input
- All input files must have a `segments` array OR be a list of segments
