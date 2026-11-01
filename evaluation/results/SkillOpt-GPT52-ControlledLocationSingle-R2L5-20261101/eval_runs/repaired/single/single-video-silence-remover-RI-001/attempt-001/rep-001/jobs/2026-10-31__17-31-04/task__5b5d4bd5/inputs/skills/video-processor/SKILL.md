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
3. Detect the non-teaching opening with the silence detector's result, then start long-pause detection at that returned boundary **on the same original media timeline**. The silence-detector outputs **timestamps in seconds aligned to the original video/audio timeline (post-fix / after any trimming offset corrections in the detector)**—do not re-base to 0 at the boundary, and do not apply any implicit smoothing-window center/half-window shift. Run the documented detector defaults before considering any tuning.
4. Combine, sort, clamp, and de-overlap all removal segments **using timestamps in seconds on the original video timeline**. Clamp to `[0, original_duration]` without changing timebase, preserve every positive gap, and merge only overlapping or touching intervals. When combining outputs from multiple detectors/stages, pass detector timestamps through unchanged unless a stage explicitly emits a documented correction. Do not re-base timestamps to the trimmed opening boundary, subtract `silence_end`, or apply smoothing-window center/half-window offsets before segment merging or ffmpeg processing.

   Invoke pause detection with `--start-time` set directly to the silence detector's returned `silence_end` value from the original timeline. Do not subtract the opening duration, add smoothing/window compensation, or shift timestamps relative to trimmed media unless a detector explicitly documents a corrective transform.
5. Process the original video with the combined segments to create the compressed video.
6. Generate the task-format compression report from the actual original video, compressed video, and final segment list.
7. Verify both outputs with tools and repair any failed check.

For `video-silence-remover`, completion requires both `/root/compressed_video.mp4` and `/root/compression_report.json`. Before finishing, confirm that:

- both files exist and are non-empty;
- `ffprobe` can read the compressed video and reports valid video and audio streams;
- the JSON is parseable and contains `original_duration_seconds`, `compressed_duration_seconds`, `removed_duration_seconds`, `compression_percentage`, and `segments_removed`;
- every removed segment has numeric `start < end` and `duration ≈ end - start`, and the segments are sorted and non-overlapping;


- detector-derived timestamps remain aligned to the original media timeline (i.e., no systematic offset from smoothing-window alignment or boundary re-basing);
- each positive gap between detector outputs remains in the keep list, and parameter choices are supported by signal evidence rather than a target compression total;
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


### Timestamp Alignment Requirement (Silence Removal)

- All segment timestamps (`start`, `end`) are **in seconds on the original input video timeline**.
- If any upstream audio preprocessing uses smoothing/windowing, timestamps must still map to the **correct original-time positions** (avoid assuming the smoothed value is centered unless the detector explicitly compensates).
- Downstream steps (pause detection, segment merging, clamping, and ffmpeg `trim/atrim`) must consume these original-timeline timestamps directly; do not re-index time from the opening boundary.


- Example detector wiring on the original timeline:

```bash
# 1. Detect opening on original timeline
python3 detect_silence.py \
  --input /root/audio.wav \
  --output /root/opening.json

# 2. Read silence_end from opening.json and pass it through unchanged
python3 detect_pauses.py \
  --input /root/audio.wav \
  --start-time 37.42 \
  --output /root/pauses.json

# 3. Combine original-timeline removal segments without rebasing
python3 combine_segments.py \
  --inputs /root/opening.json /root/pauses.json \
  --output /root/final_segments.json

# 4. Process the original video using the combined original-timeline segments
python3 /root/.claude/skills/video-processor/scripts/process_video.py \
  --input /root/input_video.mp4 \
  --output /root/compressed_video.mp4 \
  --remove-segments /root/final_segments.json
```
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

- Preserves video quality using CRF encoding
- Maintains audio sync throughout
- Handles edge cases (segments at start/end of video)
- Generates detailed statistics for verification
