---
name: ffmpeg-media-info
description: Inspect media properties (duration, codecs, sample rate, channels) with
  ffprobe/ffmpeg for verification and debugging.
---

## Steps
1. Quick inspection:
   - `ffmpeg -i input.mp4`
2. Full JSON metadata:
   - `ffprobe -v quiet -print_format json -show_format -show_streams input.mp4`
3. Duration (seconds):
   - `ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 input.mp4`
4. Audio stream properties (verify **48 kHz mono**, codec, etc.):
   - Sample rate:  
     `ffprobe -v error -select_streams a:0 -show_entries stream=sample_rate -of default=noprint_wrappers=1:nokey=1 input.mp4`
   - Channels:  
     `ffprobe -v error -select_streams a:0 -show_entries stream=channels -of default=noprint_wrappers=1:nokey=1 input.mp4`
   - Codec name:  
     `ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of default=noprint_wrappers=1 input.mp4`
## Expected Result
You can confirm output deliverables meet required technical specs (e.g., WAV is pcm_s16le 48 kHz mono; MP4 audio is 48 kHz mono) and verify durations for drift checks.
