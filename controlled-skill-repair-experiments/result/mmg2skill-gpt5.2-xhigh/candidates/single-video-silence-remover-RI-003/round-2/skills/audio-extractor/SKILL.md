---
name: audio-extractor
description: Extract audio from a video to a mono 16kHz PCM WAV for downstream energy/silence
  analysis.
---

## Steps
1. Locate the provided input video (for this task: `data/input_video.mp4`) and probe duration with ffprobe (use this later for segment clamping/validation):
   ```bash
   ls -lh data/input_video.mp4
   ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 /path/to/video.mp4
   ```
2. Run the bundled extractor script from the workspace (do **not** assume a global `/root/.claude/skills/...` path):
   ```bash
   python3 audio-extractor/scripts/extract_audio.py \
     --video /path/to/video.mp4 \
     --output /path/to/audio.wav
   ```
   Optional flags: `--sample-rate 16000` (default), `--duration <seconds>`.
3. If you cannot access the script for any reason, run the equivalent ffmpeg command directly:
   ```bash
   ffmpeg -i /path/to/video.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 /path/to/audio.wav -y
   ```
4. Confirm the WAV exists and is readable (non-empty; mono; ~16kHz).

## Expected Result
A non-empty WAV file (PCM s16le, mono, 16kHz by default) ready for `energy-calculator`.
