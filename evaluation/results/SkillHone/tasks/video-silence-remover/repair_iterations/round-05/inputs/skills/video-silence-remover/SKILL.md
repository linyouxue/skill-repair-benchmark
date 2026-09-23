---
name: video-silence-remover
description: Run an end-to-end, dependency-light video silence removal pipeline.
---

# Video silence removal

Use `run_pipeline.py` as the single entrypoint. It extracts mono PCM audio, computes
standard-library RMS windows, detects and normalizes pause segments, removes them
with ffmpeg, and writes a machine-readable compression report.

```bash
python3 skills/video-silence-remover/run_pipeline.py \
  --input /root/input_video.mp4 \
  --output /root/compressed_video.mp4 \
  --report /root/compression_report.json
```

The Python standard library is sufficient for analysis. `ffmpeg` and `ffprobe` are
required for media I/O; the entrypoint checks both before creating output files and
reports actionable errors when either is unavailable.
