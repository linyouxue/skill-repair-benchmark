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
    --merge-gap 0.01 \
    --output /path/to/all_segments.json
```

### Parameters

- `--segments`: One or more segment JSON files to combine
- `--output`: Path to output combined segments JSON
- `--merge-gap`: Merge segments whose gap is ≤ this many seconds (default: `0`). Useful to absorb rounding artifacts and ensure non-overlap.
- `--clamp-end`: Optional maximum timestamp to clamp segment ends (e.g., the video duration)

### Time / interval convention

All timestamps are in seconds on the original timeline, using half-open intervals: **`[start, end)`** (start is inclusive, end is exclusive).

### Input Format

Each input file may be one of the following:

1. A dict with a `segments` array (recommended)
2. A bare JSON list of segments
3. A single segment object with `start` and `end`

Example (dict with `segments`):

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

- Output segments are **sorted, clamped (if requested), and merged** to ensure they are **non-overlapping**.
- Adjacent/touching segments are merged when `--merge-gap 0`.
- Compatible with video-processor `--remove-segments` input.
