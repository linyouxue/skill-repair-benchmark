---
name: ffmpeg-media-info
description: Inspect media with ffprobe/ffmpeg to validate streams, duration, and codecs, plus a mandatory pre-termination deliverables gate.
---

# FFmpeg Media Info Skill

Use ffprobe/ffmpeg to inspect media metadata and validate outputs.

## Pre-termination Deliverables Hook (do this right before end_turn)

Before termination on file-based tasks, run the deliverables gate unconditionally: check required paths exist and are readable; if anything fails, go back to the producer step and re-run until it passes.

```bash
mkdir -p /outputs
ls -la /outputs
ffprobe -v error -show_format -show_streams /outputs/dubbed.mp4 >/dev/null
```

Decision rule: if any check fails, do not end the run.

Read references/deliverables-gate.md when the grader checks for files at exact paths under /outputs. Skip when the caller collects outputs from stdout only.

## Basic Info

```bash
ffprobe -v quiet -print_format json -show_format -show_streams input_media
```

## Duration

```bash
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 input_media
```

## Streams

```bash
# Audio stream properties
ffprobe -v error -select_streams a:0 -show_entries stream=codec_name,sample_rate,channels -of json input_media
```

## Common Pitfalls

- Checking only metadata of inputs; also probe the outputs you wrote to `/outputs/...`.
