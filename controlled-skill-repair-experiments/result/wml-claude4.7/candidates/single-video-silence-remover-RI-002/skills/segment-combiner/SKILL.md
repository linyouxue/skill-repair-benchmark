---
name: segment-combiner
description: Combine multiple segment detection results into a normalized interval union. Use when you need to merge segments from different detectors, prepare removal lists for video processing, or consolidate detection outputs into a disjoint, sorted, clamped sequence.
---

# Segment Combiner

Combines multiple segment JSON files into a single, normalized unified segments file for video processing. The output is the **interval union** of all inputs, not a plain concatenation.

## Use Cases

- Merging segments from multiple detectors (e.g., initial-silence + pauses)
- Consolidating detection results that may touch or overlap at boundaries
- Preparing unified input for video-processor that satisfies its precondition contract

## Usage

```bash
python3 /root/.claude/skills/segment-combiner/scripts/combine_segments.py \
    --segments /path/to/segments1.json /path/to/segments2.json \
    --output /path/to/all_segments.json \
    --total-duration 600.0
```

### Parameters

- `--segments`: One or more segment JSON files to combine
- `--output`: Path to output combined segments JSON
- `--total-duration`: Optional video duration in seconds. When provided, segment ends are clamped to `total_duration` and starts are clamped to `0`. Strongly recommended when the output feeds `video-processor`, so the downstream precondition check cannot fail on out-of-range intervals.

### Input Format

Each input file should have a `segments` array:

```json
{
  "segments": [
    {"start": 0, "end": 221, "duration": 221},
    {"start": 219, "end": 305, "duration": 86}
  ]
}
```

### Output Format

```json
{
  "segments": [
    {"start": 0, "end": 305, "duration": 305}
  ],
  "total_segments": 1,
  "total_duration_seconds": 305
}
```

## Normalization post-conditions (contract)

The `segments` array returned by this skill is guaranteed to be a normalized
interval union. Downstream tools (notably `video-processor`) rely on these
properties and may refuse to proceed if they do not hold:

1. **Sorted** by `start` ascending.
2. **Clamped** so every `start >= 0` and, when `--total-duration` is given,
   every `end <= total_duration`. Degenerate intervals with `end <= start` after
   clamping are dropped.
3. **Disjoint and non-touching**: for consecutive segments `end[i] < start[i+1]`.
   Any overlapping *or touching* input intervals (e.g., opening ending at `221`
   plus a pause starting at `221` or `219`) are merged into one.
4. **Consistent duration**: for every segment `duration == end - start` after
   merging. Durations are recomputed; input `duration` fields are not trusted.

These post-conditions are the mechanism this skill is responsible for; detector
threshold tuning, start-time handoff, and min-duration inclusivity remain the
responsibility of the respective detectors and must not be re-litigated here.

## Dependencies

- Python 3.11+

## Example

```bash
# Combine segments from multiple detectors into a normalized union
python3 /root/.claude/skills/segment-combiner/scripts/combine_segments.py \
    --segments initial_silence.json pauses.json \
    --total-duration 600 \
    --output all_segments.json
```

## Notes

- Output is the interval union: sorted, clamped to `[0, total_duration]`,
  with overlapping/touching intervals merged, and each `duration` recomputed.
- Compatible with `video-processor --remove-segments` input and satisfies its
  "sorted and non-overlapping" precondition by construction.
- All input files must have a `segments` array.
