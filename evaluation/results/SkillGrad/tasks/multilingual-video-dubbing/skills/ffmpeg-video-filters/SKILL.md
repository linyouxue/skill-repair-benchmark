---
name: ffmpeg-video-filters
description: Apply video filters with ffmpeg and enforce a mandatory pre-termination deliverables gate for file-based tasks.
---

# FFmpeg Video Filters Skill

Apply common video filters (scale, crop, overlays, speed, color).

## Pre-termination Deliverables Hook (do this right before end_turn)

Before termination on file-based tasks, run the deliverables gate unconditionally: confirm required paths exist and outputs are readable; if not, go back to the producing step and re-check.

```bash
mkdir -p /outputs
ls -la /outputs
ffprobe -v error -show_format -show_streams /outputs/dubbed.mp4 >/dev/null
```

Decision rule: do not end the run until the hook passes.

Read references/deliverables-gate.md when the grader checks for files at exact paths under /outputs. Skip when the caller collects outputs from stdout only.

## Scaling

```bash
ffmpeg -i input_video -vf scale=-2:720 output_video
```

## Overlay

```bash
ffmpeg -i input_video -i overlay_image -filter_complex "overlay=10:10" output_video
```

## Notes

- Filter correctness should be verified on the written output (probe or play a short excerpt).

## Common Pitfalls

- Applying filters on intermediates but forgetting to export the final deliverable file.
