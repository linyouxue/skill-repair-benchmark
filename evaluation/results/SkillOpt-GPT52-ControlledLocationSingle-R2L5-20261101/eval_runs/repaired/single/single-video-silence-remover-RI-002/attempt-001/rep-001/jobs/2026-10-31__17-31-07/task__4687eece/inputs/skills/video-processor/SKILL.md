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
3. Detect the non-teaching opening with the silence detector's time-aligned result, then start long-pause detection at that returned boundary. Run the documented detector defaults before considering any tuning.
4. Combine **all** removal segments into a single **normalized merged removal-segments JSON** (the output of the segment-combiner): segments are sorted by `start`, merged/de-overlapped, and clamped to the input video duration.
5. **Pre-ffmpeg validation (must pass before calling `process_video.py`)** using the normalized merged JSON:

   - Use the segment-combiner output as the single source of truth for downstream processing and reporting.
   - Segment semantics must match the segment-combiner contract: intervals are half-open `[start, end)` in seconds, adjacent or touching intervals (`next.start <= prev.end`) are merged during normalization, and all downstream tools must consume the normalized merged result exactly as produced.
   - intervals sorted ascending by `start`;
   - non-overlapping (`next.start >= prev.end`);
   - `0 <= start < end <= video_duration_seconds` for every segment;
   - `duration` exists and matches `end - start` (within a small tolerance for float rounding).
6. Process the original video with **the normalized merged removal-segments JSON** to create `/root/compressed_video.mp4`.
7. Generate `/root/compression_report.json` in the **task-required format** using the actual original video duration, measured compressed-video duration, and the exact same normalized merged segment list passed to `process_video.py`. Do not regenerate, re-merge, or independently modify segment boundaries when producing `segments_removed`.
7. Verify both outputs with tools and repair any failed check.

For `video-silence-remover`, completion requires both `/root/compressed_video.mp4` and `/root/compression_report.json`. Before finishing, confirm that:

- both files exist and are non-empty;
- `ffprobe` can read the compressed video and reports valid video and audio streams;
- the JSON is parseable and contains exactly the task-required keys: `original_duration_seconds`, `compressed_duration_seconds`, `removed_duration_seconds`, `compression_percentage`, and `segments_removed` (array of `{start,end,duration}` objects);
- every removed segment satisfies **the normalized merged contract**: numeric `0 <= start < end <= original_duration_seconds`, `duration ≈ end - start`, segments sorted ascending by `start`, non-overlapping after merge, and no adjacent/touching intervals remain unmerged;
- `segments_removed` exactly matches the normalized merged JSON used as the removal input to `process_video.py`;
- the measured compressed duration agrees with the report and `abs(original_duration_seconds - (compressed_duration_seconds + removed_duration_seconds))` stays within a small tolerance for encoding/container rounding.

Each intermediate audio, energy, or segment file is a checkpoint, not the completion criterion. After deciding or describing the next action, perform it with a tool call. Finish only after the two final artifacts pass these checks.

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

### Input Segment Format (required normalized merged removal-segments JSON)

`process_video.py` must be given a **single normalized merged** removal-segments JSON (recommended) with this exact shape:

```json
{
  "video_duration_seconds": 3908.61,
  "segments": [
    {"start": 0.0, "end": 600.0, "duration": 600.0},
    {"start": 610.0, "end": 613.0, "duration": 3.0}
  ]
}
```

Requirements for `segments` before processing:
- sorted by `start`;
- non-overlapping and already merged;
- clamped to `[0, video_duration_seconds]`;
- each has `start < end` and `duration == end - start` (allow tiny float tolerance).


- intervals follow the normalized merged contract from the segment-combiner: half-open `[start, end)` timestamps in seconds, with adjacent/touching intervals already merged so no pair satisfies `next.start <= prev.end` after normalization.
Or multiple segment files:

```bash
python3 /root/.claude/skills/video-processor/scripts/process_video.py \
    --input video.mp4 \
    --output output.mp4 \
    --remove-segments opening.json pauses.json
```


If multiple segment files are produced by detectors, **do not** pass them directly to the final processing step for this task. First run the segment-combiner to produce one normalized merged removal-segments JSON, then pass that single merged file to `process_video.py`.

### Output

Creates the processed video and a report JSON. For `video-silence-remover`, the report **must** follow the task schema and filenames:

- Video: `/root/compressed_video.mp4`
- Report: `/root/compression_report.json`

```json
{
  "original_duration_seconds": 3908.61,
  "compressed_duration_seconds": 3078.61,
  "removed_duration_seconds": 830.0,
  "compression_percentage": 21.24,
  "segments_removed": [
    {"start": 0.0, "end": 600.0, "duration": 600.0}
  ]
}
```

## How It Works

1. **Load removal segments** from JSON file(s)
2. **Calculate keep segments** (inverse of removal segments)
3. **Build ffmpeg filter** to trim and concatenate
4. **Process video** using hardware-accelerated encoding
5. **Generate report** with statistics

### FFmpeg Filter Example

For 3 segments to keep:
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
# After combining detector outputs into one normalized merged JSON
python3 /root/.claude/skills/video-processor/scripts/process_video.py \
    --input /root/lecture.mp4 \
    --output /root/compressed.mp4 \
    --remove-segments /root/merged_removals.json

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
