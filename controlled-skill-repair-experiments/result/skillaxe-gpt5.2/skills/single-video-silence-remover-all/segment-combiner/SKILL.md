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
- `--total-duration`: (optional) Total media duration in seconds; if provided, segments are clamped to `[0, total_duration]`.
- `--merge-gap`: (optional) Merge segments whose gap is <= this many seconds (default: 0). Useful to merge back-to-back segments.

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

## Interval conventions (important)

- Segments are treated as **half-open intervals**: `[start, end)`.
- Output is **sorted, clamped (if total duration provided), and merged** so that segments are non-overlapping.
- `duration` is normalized to `end - start` in the output.

## Dependencies

- Python 3.11+

## Example

```bash
# Combine segments from multiple detectors and merge overlaps
python3 /root/.claude/skills/segment-combiner/scripts/combine_segments.py \
    --segments initial_silence.json pauses.json \
    --output all_segments.json
```

## Notes

- Output is safe to pass to video-processor as a removal list.
- If you do not clamp to total duration, ensure upstream detectors do not emit out-of-range timestamps.
