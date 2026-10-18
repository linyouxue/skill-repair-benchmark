---
name: pause-detector
description: Detect pauses and silence in audio using local dynamic thresholds. Use when you need to find natural pauses in lectures, board-writing silences, or breaks between sections. Uses local context comparison to avoid false positives from volume variation.
---

# Pause Detector

Detects pauses and low-energy segments using local dynamic thresholds on pre-computed energy data. Unlike global threshold methods, this compares energy to surrounding context, avoiding false positives when speaker volume varies.

## Use Cases

- Detecting natural pauses in lectures
- Finding board-writing silences
- Identifying breaks between sections

## Usage

```bash
python3 /root/.claude/skills/pause-detector/scripts/detect_pauses.py \
    --energies /path/to/energies.json \
    --output /path/to/pauses.json
```

### Parameters

- `--energies`: Path to energy JSON file (from energy-calculator)
- `--output`: Path to output JSON file
- `--start-time`: Start analyzing from this second (default: 0)
- `--threshold-ratio`: Ratio of local average for low energy (default: 0.5)
- `--min-duration`: Minimum pause duration in seconds (default: 2)
- `--window-size`: Local average window size (default: 30)

### Output Format


Segments are emitted in chronological order and are intended to be directly consumable by downstream segment-removal or video-combining workflows.

`start` and `end` are timestamps in seconds relative to the original media timeline. `start` is inclusive and `end` is exclusive for trimming purposes, so a segment `{ "start": 10, "end": 13 }` removes audio/video from 10.0s up to but not including 13.0s. `duration` should equal `end - start`.
```json
{
  "method": "local_dynamic_threshold",
  "segments": [
    {"start": 610, "end": 613, "duration": 3},
    {"start": 720, "end": 724, "duration": 4}
  ],
  "total_segments": 11,
  "total_duration_seconds": 28,
  "parameters": {
    "threshold_ratio": 0.5,
    "window_size": 30,
    "min_duration": 2
  }
}
```

## How It Works

1. Load pre-computed energy data
2. Calculate local average using sliding window
3. Mark seconds where energy < local_avg × threshold_ratio
4. Group consecutive low-energy seconds into segments
5. Filter segments by minimum duration

## Dependencies

- Python 3.11+
- numpy
- scipy

## Example


### Recommended Lecture / Teaching Video Preset

For lecture-style recordings with board-writing pauses or dead air, start with:

```bash
python3 /root/.claude/skills/pause-detector/scripts/detect_pauses.py \
    --energies energies.json \
    --start-time 15 \
    --threshold-ratio 0.45 \
    --min-duration 2 \
    --window-size 45 \
    --output pauses.json
```

Recommended heuristics:

- `--min-duration 2`: Good default for removing long pauses while preserving natural speech pacing.
- `--threshold-ratio 0.4-0.5`: Lower values detect more silence aggressively; increase if quiet speech is being removed.
- `--window-size 30-60`: Larger windows stabilize detection for long lectures with changing volume.
- Merge pauses separated by gaps shorter than ~0.5-1.0s before cutting video to avoid rapid jump cuts.
```bash
# Detect pauses after opening (start at 221s)
python3 /root/.claude/skills/pause-detector/scripts/detect_pauses.py \
    --energies energies.json \
    --start-time 221 \
    --output pauses.json

# Result: Found 11 pauses totaling 28 seconds
```

## Parameters Tuning

| Parameter | Lower Value | Higher Value |
|-----------|-------------|--------------|
| `threshold_ratio` | More aggressive | More conservative |
| `min_duration` | Shorter pauses | Longer pauses only |
| `window_size` | Local context | Broader context |

## Notes

- Requires energy data from energy-calculator skill
- Use --start-time to skip detected opening
- Local threshold adapts to varying speaker volume


## Integration With Video Processing

The generated `segments` array is compatible with segment-combiner and typical ffmpeg trimming workflows.

Example removal report structure:

```json
{
  "segments_removed": [
    {"start": 610, "end": 613, "duration": 3},
    {"start": 720, "end": 724, "duration": 4}
  ]
}
```

When building compressed videos, always cut using the same segment boundaries written to JSON so verification tools can reconstruct the edit timeline exactly.

## Quick Validation

Review longest detected pauses before rendering the final video:

```bash
jq '.segments | sort_by(-.duration)[:10]' pauses.json
```

Check total removed duration:

```bash
jq '[.segments[].duration] | add' pauses.json
```

If speech is accidentally removed:

- Increase `--threshold-ratio` slightly (example: `0.45` -> `0.55`)
- Increase `--min-duration` to ignore short conversational pauses
- Increase `--window-size` for smoother local averaging
