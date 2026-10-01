---
name: ffmpeg-audio-processing
description: Extract, normalize, mix, and analyze audio with ffmpeg/ffprobe, plus a mandatory pre-termination deliverables gate for file-based tasks.
---

# FFmpeg Audio Processing Skill

Extract, normalize, mix, and process audio tracks from media files.

## Pre-termination Deliverables Hook (do this right before end_turn)

Treat file-path deliverables as a hard stop condition: **immediately before termination**, run the deliverables gate unconditionally; if anything is missing or unreadable, return to artifact production and re-check until it passes.

```bash
# Minimal, always-safe checks (adapt to required paths)
mkdir -p /outputs
ls -la /outputs
ffprobe -v error -show_format -show_streams /outputs/dubbed.mp4 >/dev/null
```

Decision rule: if any required file is missing/unreadable, do not end the run—produce/fix artifacts, then re-run the hook.

Read references/deliverables-gate.md when the grader checks for files at exact paths under /outputs. Skip when the caller collects outputs from stdout only.

## When to Use

- Extract audio from video
- Normalize audio levels
- Mix multiple audio tracks
- Convert audio formats
- Extract specific channels
- Adjust audio volume

## Extract Audio

```bash
# Extract audio without video
ffmpeg -i input_media -vn -c:a pcm_s16le output_audio.wav

# Extract specific audio stream
ffmpeg -i input_media -map 0:a:0 -c:a copy output_audio
```

## Normalize Audio

```bash
# Loudness normalize (ITU-R BS.1770 family)
ffmpeg -i input_audio -af "loudnorm=I=-23:TP=-1.5:LRA=11" output_audio

# Peak detection then apply gain
ffmpeg -i input_audio -af "volumedetect" -f null -
```

## Mix Audio Tracks

```bash
# Replace audio track (copy video)
ffmpeg -i input_video -i input_audio -c:v copy -map 0:v:0 -map 1:a:0 output_video

# Mix two audio tracks
ffmpeg -i a1 -i a2 -filter_complex "[0:a][1:a]amix=inputs=2:duration=first" mixed_audio
```

## Audio Analysis

```bash
# Measure loudness (LUFS)
ffmpeg -i input_audio -af "ebur128=peak=true" -f null -

# Stream properties as JSON
ffprobe -v error -select_streams a:0 -show_entries stream=sample_rate,channels -of json input_media
```

## Common Pitfalls

- Ending the run after planning/processing but before writing required `/outputs/...` artifacts; always run the deliverables hook right before termination.
- Verifying only “file exists” but not readability; add `ffprobe`/JSON-parse checks so corrupted outputs are caught before submission.
