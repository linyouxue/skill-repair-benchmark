---
name: segment-combiner
description: Combine multiple segment detection results into a single, sorted, non-overlapping list. Use when you need to merge segments from different detectors, prepare removal lists for video processing, or consolidate detection outputs.
---

# Segment Combiner

Combines multiple segment JSON files into a single unified segments file.
Segments are sorted by start time and any overlapping or touching segments
are merged, producing a clean, disjoint list suitable for the
`video-processor` skill.

## Use Cases

- Merging segments from multiple detectors (opening + pauses)
- Consolidating detection results
- Preparing unified input for `video-processor`

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

## How It Works

1. Load every input file and collect its `segments` array.
2. Sort by `start`, then `end`.
3. Merge any segments that overlap or touch, recomputing `duration = end - start`.
4. Report total segment count and total removed duration.

## Dependencies

- Python 3.11+

## Example

```bash
# Combine detected opening with detected pauses
python3 /root/.claude/skills/segment-combiner/scripts/combine_segments.py \
    --segments initial_silence.json pauses.json \
    --output all_segments.json
```

## Notes

- Compatible with `video-processor --remove-segments` input.
- All input files must have a `segments` array.
- Overlapping/touching segments are merged — this is required for `video-processor` to compute valid keep-intervals.
