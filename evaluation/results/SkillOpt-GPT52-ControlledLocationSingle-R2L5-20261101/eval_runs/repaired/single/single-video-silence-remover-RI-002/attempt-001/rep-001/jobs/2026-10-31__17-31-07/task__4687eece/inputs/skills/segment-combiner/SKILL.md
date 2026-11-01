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


### Normalization Rules



Segment intervals use numeric `start` and `end` values measured in seconds and follow half-open interval semantics: `[start, end)`. The `start` timestamp is inclusive and the `end` timestamp is exclusive. Under this convention, segments that touch at a boundary are considered directly adjacent and must be merged to avoid gaps caused by floating-point or frame-boundary rounding.
After reading all input files, the combined segment list must be normalized before writing output:

- Validate every segment has numeric `start` and `end` values
- Clamp segment times to a non-negative timeline
- When total media duration is known or provided, clamp `end <= total_duration`
- Drop or repair invalid segments where `end <= start`
- Sort all segments by `start`
- Merge overlapping or directly-adjacent segments using the rule `next.start <= prev.end`; under the half-open `[start, end)` convention this merges both overlapping intervals and intervals that touch at the same boundary
- Recompute every output segment `duration` as `end - start`
- Recompute `total_segments` and `total_duration_seconds` from the merged output segments
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


Output guarantees:

- Output JSON contains the keys `segments`, `total_segments`, and `total_duration_seconds`
- Every output segment contains numeric `start`, `end`, and `duration` fields in seconds
- Segments use half-open interval semantics `[start, end)`
- Segments are sorted by ascending `start`
- Segments are non-overlapping after normalization and no directly-adjacent segments remain unmerged
- Segments stay within valid media bounds
- Every segment has duration consistency: `duration == end - start`
- `total_segments` equals the number of merged output segments
- `total_duration_seconds` equals the sum of merged segment durations
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


Example merge behavior for overlapping or touching intervals:

Input segments:

```json
{
  "segments": [
    {"start": 10, "end": 20},
    {"start": 18, "end": 25},
    {"start": 25, "end": 30}
  ]
}
```

Normalized output:

```json
{
  "segments": [
    {"start": 10, "end": 30, "duration": 20}
  ],
  "total_segments": 1,
  "total_duration_seconds": 20
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

- Segments are normalized, sorted, and merged before output
- Overlapping or directly-adjacent intervals are combined into a single segment
- Output is compatible with video-processor --remove-segments input and report-generator duration calculations
- All input files must have `segments` array
