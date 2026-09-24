---
name: audio-extractor
description: Extract audio from a video into a mono 16kHz WAV file for downstream
  energy/silence analysis.
---

## Steps
1. Verify prerequisites and inputs exist:
   - `ls -l data/input_video.mp4`
   - `ffmpeg -version`
2. Extract audio to WAV (mono, 16kHz PCM):
   ```bash
   python3 /root/.claude/skills/audio-extractor/scripts/extract_audio.py \
     --video data/input_video.mp4 \
     --output audio.wav
   ```
3. Confirm the WAV was created:
   - `ls -l audio.wav`
## Expected Result
An `audio.wav` file exists in the current workspace and is suitable for energy/silence analysis.
