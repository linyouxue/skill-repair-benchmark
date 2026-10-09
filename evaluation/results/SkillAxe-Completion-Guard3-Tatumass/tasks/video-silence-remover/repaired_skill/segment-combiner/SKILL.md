---
name: segment-combiner
description: Combine multiple segment detection results into a unified list. Use when you need to merge segments from different detectors, prepare removal lists for video-processor, or consolidate detection outputs.
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

## Notes

- Segments are sorted by start time
- Compatible with video-processor --remove-segments input
- All input files must have `segments` array

### Merge/normalization requirements (important for accurate cutting + reporting)

When combining segments from multiple detectors (e.g., opening + pauses), you should **normalize** the result before it is used for video cutting and before it is copied into any final report:

- Treat segments as **half-open intervals** `[start, end)`.
- **Sort** by `start`.
- **Merge** segments that overlap or touch (`next.start <= current.end`).
  - Update merged segment to `{start=min, end=max, duration=end-start}`.
- Ensure segments do not extend outside the video duration when known.

This prevents:
- double-counting removed time,
- overlapping removals that can break downstream logic,
- mismatch between “segments_removed” JSON and the audio/video actually produced.
