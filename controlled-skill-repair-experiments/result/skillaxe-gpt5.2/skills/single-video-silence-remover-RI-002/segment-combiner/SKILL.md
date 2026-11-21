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

## Interval merge contract (important)

This skill produces a **removal list** intended for downstream video cutting. To keep downstream processing reliable, the combined output MUST satisfy:

1. **Sorted** by `start` ascending.
2. **Normalized**: each segment has numeric `start < end` and `duration = end - start` (recomputed; input `duration` is treated as advisory).
3. **De-overlapped**: overlapping segments are **merged** into a single segment.
4. **Adjacency rule**: segments that touch or are separated by a tiny gap are merged to avoid micro-keeps that can create artifacts.
   - Default: merge if `next.start <= current.end + 0.05` seconds.
5. **Clamping**: if a `--total-duration` is provided, segments are clamped to `[0, total_duration]` and empty/invalid segments are dropped.

If you do not know the total duration at combine time, you may omit `--total-duration`; clamping can be done later (video-processor should still validate defensively).

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
- Output is designed to be compatible with `video-processor --remove-segments`
- All input files must have `segments` array
- Prefer combining *all* candidate removals first, then reviewing totals; do not tune detectors solely to hit a target compression percentage
