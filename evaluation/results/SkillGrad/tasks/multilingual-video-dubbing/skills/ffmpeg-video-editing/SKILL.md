---
name: ffmpeg-video-editing
description: Cut, trim, concatenate, and split video with ffmpeg, plus a mandatory pre-termination deliverables gate for file-based tasks.
---

# FFmpeg Video Editing Skill

Basic video editing: cutting, trimming, concatenating, splitting.

## Pre-termination Deliverables Hook (do this right before end_turn)

Immediately before termination, run the deliverables gate unconditionally; if any required output is missing or unreadable, return to artifact production and re-check until it passes.

```bash
mkdir -p /outputs
ls -la /outputs
ffprobe -v error -show_format -show_streams /outputs/dubbed.mp4 >/dev/null
```

Decision rule: do not end the run until the hook passes.

Read references/deliverables-gate.md when the grader checks for files at exact paths under /outputs. Skip when the caller collects outputs from stdout only.

## Cutting and Trimming

```bash
ffmpeg -ss 00:00:10 -to 00:00:30 -i input_video -c copy output_video
```

## Concatenation (file list)

```bash
ffmpeg -f concat -safe 0 -i list.txt -c copy output_video
```

## Notes

- For frame-accurate cuts, re-encode the cut segment.

## Common Pitfalls

- Cutting successfully but never writing final required deliverables; always run the deliverables hook right before termination.
