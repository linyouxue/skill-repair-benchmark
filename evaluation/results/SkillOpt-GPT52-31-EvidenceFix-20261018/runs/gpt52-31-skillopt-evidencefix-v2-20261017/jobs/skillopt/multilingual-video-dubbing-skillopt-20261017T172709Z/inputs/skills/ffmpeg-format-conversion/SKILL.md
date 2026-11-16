---
name: ffmpeg-format-conversion
description: Convert media files between formats - video containers, audio formats, and codec transcoding
---

# FFmpeg Format Conversion Skill

Convert media files between different formats and containers.

## When to Use

- Convert video containers (MP4, MKV, AVI, etc.)
- Convert audio formats (MP3, AAC, WAV, etc.)
- Transcode to different codecs
- Copy streams without re-encoding (fast)

## Basic Conversion

```bash
# Convert container format (re-encode)
ffmpeg -i input.avi output.mp4

# Copy streams without re-encoding (fast, no quality loss)
ffmpeg -i input.mp4 -c copy output.mkv

# Convert with specific codec
ffmpeg -i input.mp4 -c:v libx264 -c:a aac output.mp4
```

## Video Codec Conversion

```bash
# H.264
ffmpeg -i input.mp4 -c:v libx264 output.mp4

# H.265 (better compression)
ffmpeg -i input.mp4 -c:v libx265 output.mp4

# VP9 (web optimized)
ffmpeg -i input.mp4 -c:v libvpx-vp9 output.webm

# AV1 (modern codec)
ffmpeg -i input.mp4 -c:v libaom-av1 output.mp4
```

## Audio Format Conversion

```bash
# MP3
ffmpeg -i input.wav -acodec libmp3lame -q:a 2 output.mp3

# AAC
ffmpeg -i input.wav -c:a aac -b:a 192k output.m4a

# Opus (best quality/bitrate)
ffmpeg -i input.wav -c:a libopus -b:a 128k output.opus

# FLAC (lossless)
ffmpeg -i input.wav -c:a flac output.flac
```



### Dubbing Delivery Audio

```bash
# Professional dubbing delivery target: AAC, 48 kHz, mono
ffmpeg -i tts.wav \
  -c:a aac -b:a 192k \
  -ar 48000 -ac 1 \
  dubbed_audio.m4a
```

```bash
# Normalize and convert in one step (ITU-R BS.1770-4 style loudness target)
ffmpeg -i tts.wav \
  -af "loudnorm=I=-23:TP=-2:LRA=11" \
  -c:a aac -b:a 192k \
  -ar 48000 -ac 1 \
  mastered_audio.m4a
```
## Quality Settings

```bash
# CRF (Constant Rate Factor) - lower is better quality
ffmpeg -i input.mp4 -c:v libx264 -crf 23 output.mp4

# Bitrate
ffmpeg -i input.mp4 -b:v 2M -b:a 192k output.mp4

# Two-pass encoding (best quality)
ffmpeg -i input.mp4 -c:v libx264 -b:v 2M -pass 1 -f null /dev/null
ffmpeg -i input.mp4 -c:v libx264 -b:v 2M -pass 2 output.mp4
```

## Presets

```bash
# Encoding speed presets (faster = larger file)
ffmpeg -i input.mp4 -c:v libx264 -preset fast output.mp4
# Options: ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow

# Quality presets
ffmpeg -i input.mp4 -c:v libx264 -preset slow -crf 18 output.mp4
```

## Batch Conversion

```bash
# Convert all MKV to MP4
for f in *.mkv; do
  ffmpeg -i "$f" -c copy "${f%.mkv}.mp4"
done

# Convert with re-encoding
for f in *.avi; do
  ffmpeg -i "$f" -c:v libx264 -c:a aac "${f%.avi}.mp4"
done
```



## Multilingual Dubbing / Audio Replacement

When delivering dubbed MP4 files, explicitly map streams and force compatible audio settings. This avoids silent outputs, wrong stream selection, or incompatible sample rates.

```bash
# Replace original audio while preserving the original video stream
# -map avoids accidental stream selection from the wrong input.
ffmpeg -y \
  -i input.mp4 \
  -i dubbed.wav \
  -map 0:v:0 -map 1:a:0 \
  -c:v copy \
  -c:a aac -b:a 192k \
  -ar 48000 -ac 1 \
  -shortest \
  /outputs/dubbed.mp4
```

```bash
# Deterministic output path for scripted workflows
mkdir -p /outputs/tts_segments
ffmpeg -y -i segment.wav -ar 48000 -ac 1 /outputs/tts_segments/seg_0.wav
```

Notes:
- `-c:v copy` preserves the source video without re-encoding.
- `-ar 48000 -ac 1` enforces 48 kHz mono output for dubbing deliverables.
- `-shortest` safely trims excess audio if synthesized speech runs longer than the video.
- Use WAV/FLAC intermediates during editing; encode AAC only at final MP4 mux.
## Common Codecs

### Video
- **H.264** (libx264) - Universal compatibility
- **H.265** (libx265) - Better compression
- **VP9** (libvpx-vp9) - Open standard
- **AV1** (libaom-av1) - Modern codec

### Audio
- **AAC** (aac) - Universal
- **MP3** (libmp3lame) - Legacy
- **Opus** (libopus) - Best quality/bitrate
- **FLAC** (flac) - Lossless

## Notes

- Use `-c copy` when possible for speed (no re-encoding)
- Re-encoding is slower but allows codec/quality changes
- CRF 18-23 is good quality range for H.264
- Preset affects encoding speed vs file size tradeoff


## Validation with ffprobe

Always validate the final dubbed MP4 before delivery.

```bash
# Inspect codecs, sample rate, channels, and duration
ffprobe -v error \
  -show_entries stream=codec_name,codec_type,sample_rate,channels \
  -show_entries format=duration \
  -of json /outputs/dubbed.mp4
```

Expected dubbing delivery properties commonly include:
- Video stream preserved from source
- AAC audio codec
- 48000 Hz sample rate
- Mono (`channels=1`)
- Output duration matching source video closely


## Troubleshooting Stream Mapping

```bash
# List streams to confirm stream indexes before muxing
ffprobe -v error -show_streams input.mp4
```

Common mistakes:
- Forgetting `-map` can cause FFmpeg to keep the original audio instead of the dubbed track.
- Using `-c copy` on incompatible audio codecs can create MP4 files that fail playback.
- Omitting `-ar 48000 -ac 1` may leave inconsistent sample rates or channel layouts.
- Applying `-shortest` without checking durations can truncate intended trailing silence.
- Writing relative output paths in automation can cause missing deliverables; prefer explicit paths such as `/outputs/dubbed.mp4`.
