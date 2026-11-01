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


### Time/interval conventions (MUST follow)

- Use a consistent **half-open interval** convention for all segments: **`[start, end)`** in seconds.
  - `start` is inclusive, `end` is exclusive.
  - Require `start < end`.
  - Duration is computed as `end - start`.
- Treat timestamps returned by detectors as **timeline seconds** aligned to the original media. Any segment list passed downstream must follow `[start,end)`.
- All segment operations (sorting, merging, de-overlap, inversion to keep-segments, and ffmpeg trim/atrim) must use the same `[start,end)` convention to avoid 1-frame/1-sample overlaps or gaps.

For a silence-removal task, treat the available audio and video skills as one ordered pipeline. Continue issuing tool calls until both final artifacts pass the completion checks:

1. Extract the input video's audio.
2. Calculate the audio-energy sequence.
3. Detect the non-teaching opening using the silence detector and interpret its returned boundary as the **corrected opening end** (the exclusive `end` of `[0, opening_end)`).
4. Start long-pause detection **at `t = opening_end`** (do not search for pauses before the corrected opening boundary).
5. Combine all removal segments (opening + pauses), then **normalize** them: sort, merge, de-overlap, and **clamp to `[0, media_duration)`** before any ffmpeg processing.
5. Process the original video with the combined segments to create the compressed video.
6. Generate the task-format compression report from the actual original video, compressed video, and final segment list.
7. Verify both outputs with tools and repair any failed check.

For `video-silence-remover`, completion requires both `/root/compressed_video.mp4` and `/root/compression_report.json`. Before finishing, confirm that:

- both files exist and are non-empty;
- `ffprobe` can read the compressed video and reports valid video and audio streams;
- the JSON is parseable and contains `original_duration_seconds`, `compressed_duration_seconds`, `removed_duration_seconds`, `compression_percentage`, and `segments_removed`;
- every removed segment uses the `[start,end)` convention with numeric `start < end`, `duration ≈ end - start`, and the final list is **sorted, merged/de-overlapped, and clamped to `[0, original_duration)`** (no overlaps, no out-of-range endpoints);
- the measured compressed duration agrees with the report and `original ≈ compressed + removed`.

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

### Input Segment Format

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


### Segment normalization requirement (before ffmpeg)

When multiple sources produce removal segments (e.g., opening detector + pause detector), you MUST normalize them **before** computing keep-segments and before invoking ffmpeg:

1. Concatenate all removal segments.
2. Sort by `start`.
3. **Clamp** each segment to `[0, media_duration)`.
4. **Merge/de-overlap** using `[start,end)` semantics:
   - If `next.start <= current.end`, merge into `[current.start, max(current.end, next.end))`.
   - Drop any zero/negative-length segments after clamping.

This prevents duplicated removals, negative keep intervals, and concat failures.

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


- **Pause threshold tuning:** pause detection should be driven by relative energy. `threshold_ratio` is interpreted as a ratio of the baseline/typical energy level; **smaller values remove more (more aggressive), larger values remove less (more conservative)**. When tuning, keep opening removal fixed first, then adjust pause `min_duration` (e.g., ~2s) and `threshold_ratio` to remove true long pauses while preserving teaching.

- Preserves video quality using CRF encoding
- Maintains audio sync throughout
- Handles edge cases (segments at start/end of video)
- Generates detailed statistics for verification
