---
name: ffmpeg-audio-processing
description: Extract, normalize, mix, and process audio tracks (including ITU-R BS.1770-4
  loudness targeting) for delivery-ready outputs.
---

## Steps
1. Extract audio from a video (choose codec/format as needed):
   - WAV (uncompressed): `ffmpeg -i video.mp4 -vn -c:a pcm_s16le audio.wav`
   - AAC copy (no re-encode): `ffmpeg -i video.mp4 -vn -c:a copy audio.aac`
2. Convert to delivery specs (e.g., **48 kHz mono**):
   - `ffmpeg -i input.wav -ar 48000 -ac 1 -c:a pcm_s16le output_48k_mono.wav`
3. Measure loudness (for reporting / debugging) using an EBU R128 meter:
   - `ffmpeg -i input.wav -af ebur128=peak=true -f null -`
4. Normalize to ITU-R BS.1770-4-style targets (single-pass loudnorm):
   - `ffmpeg -i input.wav -af "loudnorm=I=-23:TP=-1.5:LRA=11" -ar 48000 -ac 1 -c:a pcm_s16le output_norm.wav`
   - Avoid relying on `loudnorm=...:measure_only=1` because some FFmpeg builds do not support that option.
5. Mix/replace audio in a video:
   - Replace audio (keep original video):  
     `ffmpeg -i video.mp4 -i new_audio.wav -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac output.mp4`
   - Mix two tracks:  
     `ffmpeg -i video.mp4 -i bg.wav -filter_complex "[0:a][1:a]amix=inputs=2:duration=first" -c:v copy output.mp4`
6. Apply delay when aligning audio:
   - `-itsoffset 0.5 -i audio.wav` (seconds), or `-af "adelay=500|500"` (ms)
## Expected Result
Audio can be extracted, resampled to 48 kHz mono, loudness-measured via `ebur128`, normalized via `loudnorm` without using unsupported options, and then mixed/muxed into a target MP4.
