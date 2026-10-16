---
name: ffmpeg-media-info
description: Inspect media properties with ffprobe/ffmpeg to verify duration, streams, codecs, and delivery constraints on final artifacts.
---

# FFmpeg Media Info Skill

Inspect media file metadata (duration, streams, codecs, sample rate, channels) and use it to verify deliverable constraints.

## Quick workflow: probe → decide → verify

1. Probe input(s) to learn duration and stream properties.
2. Decide the output constraints (container, codec, sample rate/channels, target duration).
3. Probe the **final output** to confirm it matches the constraints.

```bash
ffprobe -v error -print_format json -show_format -show_streams input.ext > in.json
ffprobe -v error -print_format json -show_format -show_streams output.ext > out.json
jq -r '.streams[] | {codec_type, codec_name, sample_rate, channels, channel_layout}' out.json
```

## Codec and container checks

```bash
# Container format name (e.g., mov,mp4,m4a,3gp,3g2,mj2)
ffprobe -v error -show_entries format=format_name -of default=nw=1:nk=1 output.ext

# Stream codecs (video/audio)
ffprobe -v error -show_entries stream=codec_type,codec_name -of csv=p=0 output.ext
```

Decision rule: if the evaluator is strict and codec acceptance is uncertain, prefer explicitly requested codecs or a lossless intermediate, then convert once constraints are confirmed.

## Duration and window sanity checks

```bash
# Duration in seconds
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 input.ext

# Audio stream duration (when present)
ffprobe -v error -select_streams a:0 -show_entries stream=duration -of default=nw=1:nk=1 output.ext
```

Read references/window-overrun-policy.md when a required segment/window extends past the source duration.
Skip when all required windows fit within the source duration.

## Common pitfalls

- Probing only inputs, then assuming outputs match constraints.
- Checking sample rate/channels but forgetting codec/container expectations.
- Reporting timing windows that exceed the delivered media duration without an explicit policy.
