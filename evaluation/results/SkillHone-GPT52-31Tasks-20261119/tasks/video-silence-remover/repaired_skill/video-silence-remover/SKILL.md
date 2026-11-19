---
name: video-silence-remover
description: End-to-end utility to remove an opening and long pauses from a teaching video by detecting low-energy segments and cutting them out. Use when you need a single command to produce compressed_video.mp4 and compression_report.json.
---

# Video Silence Remover (End-to-End)

This skill orchestrates the other skills in this bundle:

- `audio-extractor` → extract analysis audio
- `energy-calculator` → compute windowed RMS energy
- `silence-detector` → detect an initial low-content opening segment
- `pause-detector` → detect long pauses (typically > 2s)
- `segment-combiner` → merge/normalize removal segments
- `video-processor` → cut the video
- `report-generator` → emit a task-format `compression_report.json`

It is meant for automation: it produces **two task outputs** in the working directory:

- `compressed_video.mp4`
- `compression_report.json`

## Usage

```bash
python3 skills/video-silence-remover/scripts/run.py \
  --input-video data/input_video.mp4 \
  --output-video compressed_video.mp4 \
  --report compression_report.json
```

### Key options

- `--window-seconds`: Energy window size (default: 0.5). Smaller windows can find shorter pauses but increase runtime.
- `--min-pause-seconds`: Minimum pause duration to remove (default: 2.0).
- `--pause-smoothing-seconds`: Smooth energies before pause detection (default: 1.0).
- `--pause-require-absolute-gate`: More conservative pause detection; requires absolute noise-floor gate.
- `--opening-search-max`: How far from the start to search for the opening end (default: 120s).
- `--workdir`: Directory for intermediate artifacts (default: `work/`).

## Notes

- This skill relies on `ffmpeg`/`ffprobe` being available on PATH. If they are missing, it will fail with a clear message.
- Segment removal is conservative by default (prefers keeping teaching content).
- The generated report uses **measured** original/compressed durations and a **normalized** segment list.
