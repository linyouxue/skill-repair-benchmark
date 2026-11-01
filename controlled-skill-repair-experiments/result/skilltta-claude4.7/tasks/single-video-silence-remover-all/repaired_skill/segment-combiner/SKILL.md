---
name: segment-combiner
description: Combine multiple segment detection results into a sorted, merged, clamped list. Use when you need to merge segments from different detectors, prepare removal lists for video processing, or consolidate detection outputs.
---

# Segment Combiner

Combines multiple segment JSON files into a single unified segments file,
sorted by start time, with overlapping/adjacent segments merged and
(optionally) clamped to the source video duration. This produces a list
that is safe to feed into `video-processor`.

## Use Cases

- Merging segments from multiple detectors (silence + pause)
- Consolidating detection results
- Preparing unified input for video-processor

## Interval convention

All segments use the half-open convention `[start, end)` with values in
seconds. `duration = end - start`.

## Merge rule

1. Normalize each input segment to `{start, end}` (floats, seconds).
2. Drop any segment with `end <= start`.
3. Sort by `start`.
4. Walk left-to-right. Merge the next segment into the current one when
   `next.start <= current.end + gap_tolerance` (default `0.3s`). This
   handles exact overlaps, containment and tiny gaps uniformly.
5. If `--duration D` is supplied, clamp every segment to `[0, D]` and drop
   any that collapse to zero length.
6. Recompute `duration = end - start` on the final list.

The output is guaranteed to be **sorted, non-overlapping, and (if
`--duration` was supplied) within `[0, duration]`**. `video-processor`
assumes this and will double-check it defensively.

## Usage

```bash
python3 /root/.claude/skills/segment-combiner/scripts/combine_segments.py \
    --segments /path/to/segments1.json /path/to/segments2.json \
    --output /path/to/all_segments.json \
    --gap-tolerance 0.3 \
    --duration 612.4
```

### Parameters

- `--segments`: One or more segment JSON files to combine.
- `--output`: Path to output combined segments JSON.
- `--gap-tolerance`: Merge threshold in seconds (default `0.3`).
- `--duration`: Optional total video duration; when provided, segments are
  clamped to `[0, duration]`.

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
    {"start": 0.0, "end": 120.0, "duration": 120.0},
    {"start": 300.0, "end": 305.0, "duration": 5.0}
  ],
  "total_segments": 2,
  "total_duration_seconds": 125.0,
  "parameters": {
    "gap_tolerance": 0.3,
    "clamped_to_duration": 612.4,
    "interval_convention": "half_open_[start,end)"
  }
}
```

## Dependencies

- Python 3.11+

## Example

```bash
# Combine opening silence + pauses, clamp to true video duration
python3 /root/.claude/skills/segment-combiner/scripts/combine_segments.py \
    --segments initial_silence.json pauses.json \
    --duration 612.4 \
    --output all_segments.json
```

## Notes

- Always call this skill before `video-processor` so overlapping opening
  and pause segments do not produce negative-length keep ranges.
- Compatible with `video-processor --remove-segments` input.
- All input files must have a `segments` array.
