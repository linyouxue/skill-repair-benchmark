---
name: video-processor
description: Process videos by removing segments and concatenating remaining parts. Use when you need to remove detected pauses/openings from videos, create highlight reels, or batch process segment removals using ffmpeg filter_complex.
---

# Video Segment Processor

Processes videos by removing specified segments and concatenating the remaining parts. Handles multiple removal segments efficiently using ffmpeg's filter_complex.

## Use Cases

- Removing detected pauses and openings from videos
- Creating highlight reels by keeping only specific segments
- Batch processing multiple segment removals

## Usage

```bash
python3 /root/.claude/skills/video-processor/scripts/process_video.py \
    --input /path/to/input.mp4 \
    --output /path/to/output.mp4 \
    --remove-segments /path/to/segments.json
```

### Parameters

- `--input`: Path to input video file
- `--output`: Path to output video file
- `--remove-segments`: JSON file containing segments to remove

### Input Segment Format

Removal intervals use source-timeline half-open ranges `[start, end)`: `start` is included and `end` is excluded. Treat `start` and `end` as the canonical detector endpoints; do not independently round them for audio, video, filtering, or reporting. The optional `duration` field is informational and must be recomputed as `end - start` after normalization.

```json
{
  "segments": [
    {"start": 0, "end": 600, "duration": 600},
    {"start": 610, "end": 613, "duration": 3}
  ]
}
```

Or multiple segment files:

```bash
python3 /root/.claude/skills/video-processor/scripts/process_video.py \
    --input video.mp4 \
    --output output.mp4 \
    --remove-segments opening.json pauses.json
```

### Output

Creates the processed video and a report JSON:

```json
{
  "original_duration": 3908.61,
  "output_duration": 3078.61,
  "removed_duration": 830.0,
  "compression_percentage": 21.24,
  "segments_removed": 91,
  "segments_kept": 91
}
```

## How It Works

1. **Probe the source** for duration, video streams, and whether an audio stream exists.
2. **Normalize the canonical removal intervals** by validating finite endpoints, clamping them to the source timeline, sorting them, and merging overlaps or touching ranges without rounding.
3. **Derive one ordered keep-range list** as the exact inverse of the normalized removals; use this same list and the same endpoint values for both video and audio.
4. **Build a stable filter graph** that trims each keep range, resets timestamps, and concatenates in order; use video-only processing when the source has no audio.
5. **Encode, probe, and decode-check the result** before generating statistics or reporting success.

### FFmpeg Filter Example

For each keep range `[start, end)`, use the same `start` and `end` values for both streams, reset timestamps before concatenation, and preserve list ordering. For example, for two ranges:
```
[0:v]trim=start=600:end=610,setpts=PTS-STARTPTS[v0];
[0:a]atrim=start=600:end=610,asetpts=PTS-STARTPTS[a0];
[0:v]trim=start=613:end=1000,setpts=PTS-STARTPTS[v1];
[0:a]atrim=start=613:end=1000,asetpts=PTS-STARTPTS[a1];
[v0][v1]concat=n=2:v=1:a=0[outv];
[a0][a1]concat=n=2:v=0:a=1[outa]
```

## Dependencies

- ffmpeg with libx264 and aac support
- Python 3.11+

## Limitations

- Processing time: ~0.3× video duration (e.g., 20 min for 65 min video)
- Requires sufficient disk space (output ≈ 70-80% of input size)
- May have frame-accurate cuts (not sample-accurate)

## Example

```bash
# Process video with opening and pause removal
python3 /root/.claude/skills/video-processor/scripts/process_video.py \
    --input /root/lecture.mp4 \
    --output /root/compressed.mp4 \
    --remove-segments /root/opening.json /root/pauses.json

# Result: 65 min → 51 min (21.2% compression)
```

## Performance Tips

- Use `-preset medium` for balanced speed/quality
- Use `-crf 23` for good quality at reasonable size
- Process on machines with 2+ CPU cores for faster encoding

## Notes

- Preserves video quality using CRF encoding
- Maintains audio sync throughout
- Handles edge cases (segments at start/end of video)
- Generates detailed statistics for verification



## Acceptance Contract

Treat the normalized removal intervals and their derived keep ranges as the single source of truth. Keep ranges must cover the source timeline outside removals, be ordered, and use half-open endpoints. This must correctly handle removal at the start, removal at the end, adjacent or overlapping removals, no removals, and a source with no audio. If no positive keep range remains, fail rather than emitting an invalid concat graph.

For every keep range, trim video with `trim` and audio with `atrim` when audio exists, then apply `setpts=PTS-STARTPTS` and `asetpts=PTS-STARTPTS`. Concatenate video and audio separately with identical keep-range counts and ordering. Do not round or independently recalculate endpoints between streams. Map only streams that exist; a video-only input must produce a valid video-only output.

Before report generation, predict the kept duration from the normalized keep ranges and compare it with the probed output duration and each output stream duration. Accept only finite values within an explicit tolerance of 0.25 seconds (or the tighter precision supported by the probe); reject unexplained drift, missing expected streams, non-positive output, timestamp inconsistencies, or any `ffmpeg -v error` decode failure. Generate the report only after these checks pass, using measured source and output durations, the normalized removal intervals, and arithmetic consistent with the predicted kept duration within that tolerance.
