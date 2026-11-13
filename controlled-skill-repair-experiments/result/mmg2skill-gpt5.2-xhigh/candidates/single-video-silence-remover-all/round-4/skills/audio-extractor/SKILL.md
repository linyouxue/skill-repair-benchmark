---
name: audio-extractor
description: Extract mono 16kHz PCM WAV audio from a video for downstream energy/silence
  analysis.
---

## Steps
1. Run the extractor script:
   ```bash
   python3 /root/.claude/skills/audio-extractor/scripts/extract_audio.py \
     --video data/input_video.mp4 \
     --output /root/audio.wav
   ```
   - Optional: `--sample-rate` (default `16000`), `--duration` (seconds, default full video).
2. Confirm the WAV exists and is non-empty (e.g., `ls -lh /root/audio.wav`).

## Expected Result
A readable WAV file at the requested path (mono, 16kHz, PCM s16le) suitable for energy calculation.
