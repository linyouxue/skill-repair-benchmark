---
name: ffmpeg-format-conversion
description: Convert containers/codecs with ffmpeg and apply a mandatory pre-termination deliverables gate for file-based tasks.
---

# FFmpeg Format Conversion Skill

Convert media files between formats, containers, and codecs.

## Pre-termination Deliverables Hook (do this right before end_turn)

Immediately before termination, run a deliverables gate unconditionally: verify each required output exists at the exact required path and is minimally readable; if not, return to the producing step and re-check until it passes.

```bash
mkdir -p /outputs
ls -la /outputs
ffprobe -v error -show_format -show_streams /outputs/dubbed.mp4 >/dev/null
```

Decision rule: do not end the run until the hook passes.

Read references/deliverables-gate.md when the grader checks for files at exact paths under /outputs. Skip when the caller collects outputs from stdout only.

## Basic Conversion

```bash
# Re-container without re-encode
ffmpeg -i input_media -c copy output_media

# Transcode video + audio
ffmpeg -i input_media -c:v libx264 -c:a aac output_media
```

## Audio Format Conversion

```bash
# WAV to AAC
ffmpeg -i input_audio.wav -c:a aac -b:a 192k output_audio.m4a

# Resample and set channels
ffmpeg -i input_audio -ar 48000 -ac 1 output_audio.wav
```

## Notes

- Prefer `-c copy` only when container/codec already matches requirements.
- For delivery constraints (sample rate/channels), set them explicitly during conversion.

## Common Pitfalls

- Assuming a converted file is valid because ffmpeg exited 0; always `ffprobe` the written output.
