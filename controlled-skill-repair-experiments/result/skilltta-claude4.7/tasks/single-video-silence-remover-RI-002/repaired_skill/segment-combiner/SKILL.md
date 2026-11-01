---
name: segment-combiner
description: Combine multiple segment detection results into a unified, sorted, non-overlapping list using the project's half-open [start, end) interval convention. Use when you need to merge segments from different detectors, prepare removal lists for video processing, or consolidate detection outputs.
---

# Segment Combiner

Combines multiple segment JSON files into a single unified segments file for video processing. Enforces the project-wide half-open `[start, end)` interval convention and merges adjacent/overlapping intervals with a configurable gap tolerance.

## Use Cases

- Merging segments from multiple detectors (opening + pauses)
- Consolidating detection results into a clean removal list
- Preparing unified input for `video-processor --remove-segments`

## Usage

```bash
python3 /root/.claude/skills/segment-combiner/scripts/combine_segments.py \
    --segments /path/to/segments1.json /path/to/segments2.json \
    --output /path/to/all_segments.json
```

### Parameters

- `--segments`: One or more segment JSON files to combine
- `--output`: Path to output combined segments JSON
- `--gap-eps`: Merge two intervals when `next.start - current.end <= gap_eps` seconds (default: `0.2`)
- `--min-duration`: Optional minimum merged duration to retain. **No default** — the combiner must not silently drop the opening segment or short-but-valid pauses already filtered upstream.

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
  "parameters": {"gap_eps": 0.2, "min_duration": null}
}
```

## Interval Convention (project-wide)

- Intervals are **half-open `[start, end)`**, floats, seconds. `end` is exclusive.
- Entries are coerced to float; `start` is clamped to `>= 0`; any entry with `end <= start` is dropped.
- Segments are sorted by `start` ascending.
- Two consecutive intervals are merged when `next.start - current.end <= gap_eps` (default `GAP_EPS = 0.2s`). This includes strict overlap and small gaps that would otherwise leave sub-second speech slivers.
- After merging, `duration = end - start` is recomputed on each interval and `total_duration_seconds` is recomputed from the merged list.
- The output is guaranteed sorted, strictly non-overlapping (`prev.end < next.start`), and `end > start` for every entry.

## Dependencies

- Python 3.11+

## Example

```bash
# Combine opening silence + detected pauses into one clean removal list
python3 /root/.claude/skills/segment-combiner/scripts/combine_segments.py \
    --segments initial_silence.json pauses.json \
    --output all_segments.json
```

## Notes

- Output is sorted, non-overlapping, and uses half-open `[start, end)` intervals.
- `duration` and `total_duration_seconds` are recomputed from the merged intervals; do not trust pre-merge sums.
- Compatible with `video-processor --remove-segments`, which re-applies the same normalization defensively.
- If you need to preserve a very short interval (e.g. the opening when `speech_start` is < 2s into the file), pass it in explicitly; the combiner does not drop by duration unless `--min-duration` is set.
