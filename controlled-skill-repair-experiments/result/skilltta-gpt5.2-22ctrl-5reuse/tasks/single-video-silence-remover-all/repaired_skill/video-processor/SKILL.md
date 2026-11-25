---
name: video-processor
description: Process videos by removing segments and concatenating remaining parts. Use when you need to remove detected pauses/openings from videos, create highlight reels, or batch process segment removals using ffmpeg filter_complex.
---

# Video Segment Processor

## Blocking terminal-result gate

For `video-silence-remover`, execution state is **RED** until terminal tool results confirm both required artifacts and every completion check below. While state is RED, every assistant response must include an actual `terminal` function call for the next incomplete pipeline action; status text may accompany that call.

A command written in prose, JSON, or a code block is still pending because it has no terminal result. Advance a step only after its real tool result returns. State becomes **GREEN** only after tool results confirm `/root/compressed_video.mp4` and `/root/compression_report.json`; an ordinary final response is valid only in GREEN state.

Processes videos by removing specified segments and concatenating the remaining parts. Handles multiple removal segments efficiently using ffmpeg's filter_complex.

## Mandatory end-to-end completion gate

For a silence-removal task, treat the available audio and video skills as one ordered pipeline. Continue issuing tool calls until both final artifacts pass the completion checks:

1. Extract the input video's audio.
2. Calculate the audio-energy sequence.
3. Detect the non-teaching opening with the silence detector's result, then start long-pause detection at that returned boundary.
4. Combine, sort, clamp, and de-overlap all removal segments.
5. Process the original video with the combined segments to create the compressed video.
6. Generate the task-format compression report from the actual original video, compressed video, and final segment list.
7. Verify both outputs with tools and repair any failed check.

For `video-silence-remover`, completion requires both `/root/compressed_video.mp4` and `/root/compression_report.json`. Before finishing, confirm that:

- both files exist and are non-empty;
- `ffprobe` can read the compressed video and reports valid video and audio streams;
- the JSON is parseable and contains `original_duration_seconds`, `compressed_duration_seconds`, `removed_duration_seconds`, `compression_percentage`, and `segments_removed`;
- every removed segment has numeric `start < end` and `duration ≈ end - start`, and the segments are sorted and non-overlapping;
- the measured compressed duration agrees with the report and `original ≈ compressed + removed`.

Each intermediate audio, energy, or segment file is a checkpoint, not the completion criterion. After deciding or describing the next action, perform it with a tool call. Finish only after the two final artifacts pass these checks.

## Contract (important)

- **Time unit**: seconds (float)
- **Interval convention**: **half-open** intervals `[start, end)`
- **Duration**: `duration = end - start`

This processor will defensively **sort, clamp to video duration, and merge** overlapping/adjacent removal segments internally before computing keep segments.

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
- `--remove-segments`: JSON file(s) containing segments to remove
- `--eps`: Merge epsilon in seconds used when merging adjacent/overlapping removal segments (default: 1e-3)

### Input Segment Format

```json
{
  "segments": [
    {"start": 0.0, "end": 600.0, "duration": 600.0},
    {"start": 610.0, "end": 613.0, "duration": 3.0}
  ]
}
```

Notes:
- `duration` is recommended but the processor will recompute `duration = end - start` after clamping/merging.
- Segments are treated as half-open intervals `[start,end)`.

Or multiple segment files:

```bash
python3 /root/.claude/skills/video-processor/scripts/process_video.py \
    --input video.mp4 \
    --output output.mp4 \
    --remove-segments opening.json pauses.json
```

### How It Works

1. **Load removal segments** from JSON file(s)
2. **Clamp + merge** removal segments (sorted, non-overlapping)
3. **Calculate keep segments** (inverse of merged removal segments)
4. **Build an ffmpeg filtergraph**
   - For multiple keep segments, uses `split`/`asplit` + `trim`/`atrim` + `concat` (avoids multi-consuming `[0:v]`/`[0:a]`)
   - If the input has no audio stream, processes video-only (`-an`)
5. **Process video** using libx264 + AAC
6. **Generate an internal verification report** alongside the output video

### FFmpeg Filter Example

For 2 segments to keep (schematic):
```
[0:v]split=2[v0][v1];
[0:a]asplit=2[a0][a1];
[v0]trim=start=600:end=610,setpts=PTS-STARTPTS[v0t];
[a0]atrim=start=600:end=610,asetpts=PTS-STARTPTS[a0t];
[v1]trim=start=613:end=1000,setpts=PTS-STARTPTS[v1t];
[a1]atrim=start=613:end=1000,asetpts=PTS-STARTPTS[a1t];
[v0t][v1t]concat=n=2:v=1:a=0[outv];
[a0t][a1t]concat=n=2:v=0:a=1[outa]
```

## Dependencies

- ffmpeg with libx264 and aac support
- Python 3.11+

## Notes

- Maintains audio sync by trimming audio and video together
- Handles edge cases (segments at start/end of video)
- Defensively merges overlaps to avoid invalid keep segments
