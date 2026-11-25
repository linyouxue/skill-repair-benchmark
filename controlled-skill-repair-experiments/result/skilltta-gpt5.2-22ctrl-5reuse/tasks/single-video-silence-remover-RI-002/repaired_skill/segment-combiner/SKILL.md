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

### Optional normalization/merge parameters

```bash
python3 /root/.claude/skills/segment-combiner/scripts/combine_segments.py \
    --segments opening.json pauses.json \
    --merge-gap 0.1 \
    --total-duration 600.0 \
    --output all_segments.json
```

- `--merge-gap`: Merge intervals if `next.start <= current.end + merge_gap`.
  - Default: `0.1` seconds.
  - Purpose: prevents micro-gaps from creating tiny keep-clips and excess cuts.
- `--total-duration`: Optional clamp window `[0, total_duration]` (seconds). Recommended when known.

### Parameters

- `--segments`: One or more segment JSON files to combine
- `--output`: Path to output combined segments JSON

## Interval convention (important)

All segments represent **removed** time intervals in **seconds** using the half-open convention:

- Interval is `[start, end)`
- Duration must be `end - start`

## Normalization and merge contract

This skill guarantees the output `segments` list is:

1. **Numeric**: `start`/`end` are numbers (float allowed).
2. **Valid**: segments with `end <= start` are dropped.
3. **Optionally clamped**: if `--total-duration` is provided, segments are clamped to `[0, total_duration]`.
4. **Sorted and non-overlapping**: segments are sorted by `start` and merged when overlapping or within `--merge-gap`.
5. **Duration is recomputed**: the script does **not** trust any input `duration`; it always writes `duration = end - start`.

## Input Format

Each input file may be any of the following:

1) A dict with a `segments` array:
```json
{
  "segments": [
    {"start": 0, "end": 120, "duration": 120},
    {"start": 300, "end": 305, "duration": 5}
  ]
}
```

2) A raw list of segment dicts:
```json
[
  {"start": 0, "end": 120},
  {"start": 300, "end": 305}
]
```

3) A single segment dict:
```json
{"start": 0, "end": 120}
```

Notes:
- The `duration` field is optional in inputs and is ignored if present.

## Output Format

```json
{
  "segments": [
    {"start": 0.0, "end": 120.0, "duration": 120.0},
    {"start": 300.0, "end": 305.0, "duration": 5.0}
  ],
  "total_segments": 2,
  "total_duration_seconds": 125.0
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

- Output segments are sorted, merged (no overlaps), and ready for `video-processor --remove-segments`
- Use `--total-duration` when running standalone, to prevent out-of-range timestamps
