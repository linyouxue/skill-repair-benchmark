---
name: segment-combiner
description: Combine multiple segment detection results into a sorted, non-overlapping list. Use when you need to merge segments from different detectors, prepare removal lists for video processing, or consolidate detection outputs.
---

# Segment Combiner

Combines multiple segment JSON files into a single unified segments file for
video processing. The output is guaranteed to be sorted and non-overlapping so
it can be consumed directly by `video-processor --remove-segments` without any
additional cleanup.

## Use Cases

- Merging segments from multiple detectors (e.g. initial silence + pauses)
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

Inputs do not need to be sorted or disjoint; segments that overlap or touch
across files (for example an initial-silence segment `[0, 221]` and a pause
segment `[218, 225]`) are merged into a single interval by the combiner.

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

## Output Contract

The combiner guarantees (and downstream consumers may rely on):

1. `segments` is sorted by `start` ascending.
2. `segments` is non-overlapping: for every adjacent pair, `next.start > current.end`.
3. Overlapping or touching inputs are **merged** into
   `[min(starts), max(ends)]` so no second of the original timeline is counted
   twice.
4. Each output segment satisfies `start < end` and
   `duration == end - start`.
5. `total_duration_seconds` is the sum of `duration` over the MERGED intervals
   (not the raw inputs), giving the true amount of time to be removed.

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

- Output is directly compatible with `video-processor --remove-segments`;
  the video processor assumes the sorted / non-overlapping contract above and
  will produce incorrect keep-ranges if that contract is violated.
- All input files must contain a `segments` array.
