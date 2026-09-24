---
name: ffmpeg-format-conversion
description: Convert media files between containers/codecs, including stream-copy
  and re-encode workflows.
---

## Steps
1. Convert container (re-encode defaults):
   - `ffmpeg -i input.avi output.mp4`
2. Copy streams without re-encoding (fast, no quality loss):
   - `ffmpeg -i input.mp4 -c copy output.mkv`
3. Transcode with explicit codecs:
   - `ffmpeg -i input.mp4 -c:v libx264 -c:a aac output.mp4`
4. Audio-only conversions:
   - MP3: `ffmpeg -i input.wav -c:a libmp3lame -q:a 2 output.mp3`
   - AAC: `ffmpeg -i input.wav -c:a aac -b:a 192k output.m4a`
   - Opus: `ffmpeg -i input.wav -c:a libopus -b:a 128k output.opus`
   - FLAC: `ffmpeg -i input.wav -c:a flac output.flac`
5. Quality control (H.264 example):
   - `ffmpeg -i input.mp4 -c:v libx264 -crf 23 -c:a aac output.mp4`
6. Batch convert patterns (shell loops) as needed.
## Expected Result
Files are converted to required containers/codecs, using either stream copy (`-c copy`) or controlled re-encoding.
