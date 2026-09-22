---
name: video-processor
description: Process videos by removing segments and concatenating remaining parts, and always materialize and verify required deliverables before finishing.
---

# Video Segment Processor

Processes videos by removing specified segments and concatenating the remaining parts. Handles multiple removal segments efficiently using ffmpeg's filter_complex.

## Workflow: Finish With Verified Deliverables

1. Write down the required deliverables (exact paths + formats) and treat them as **blocking** output requirements.
2. Choose the shortest end-to-end pipeline that *writes* those deliverables (do not stop at intermediate JSONs like energies/segments).
3. Treat **"no pipeline/skill invocations ran"** as an automatic deliverables-gate failure whenever file outputs are required.
4. Materialize each deliverable to disk and then verify: existence, non-empty size, and basic readability (e.g., JSON parses and has required top-level keys).
5. **Termination precondition (mandatory):** before ending the run, explicitly list every required deliverable and a PASS/FAIL result for (a) existence, (b) non-empty size, and (c) parse/schema validation when applicable; **only PASS for all files permits `end_turn`.**
6. If any check fails, immediately run the minimal pipeline that writes the missing/invalid files (fix filenames/paths first), then re-run the deliverables gate; never end the turn without recorded PASS results.

Read references/materialize-deliverables.md when the evaluation expects specific output files (e.g., a processed video plus a JSON report). Skip when you are returning only console output and no files are required.

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

## Performance Tips

- Use `-preset medium` for balanced speed/quality
- Use `-crf 23` for good quality at reasonable size
- Process on machines with 2+ CPU cores for faster encoding

## Common Pitfalls

- Ending the run before invoking any skills or writing the required output files.
- Ending the run after computing segments but before rendering the processed video and report.
- Producing files but not verifying they exist and are readable (e.g., JSON report is malformed).

## Notes

- Preserves video quality using CRF encoding
- Maintains audio sync throughout
- Handles edge cases (segments at start/end of video)
- Generates detailed statistics for verification
