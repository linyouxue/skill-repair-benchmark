---
name: ffmpeg-audio-processing
description: Extract, normalize, mix, and process audio tracks - audio manipulation and analysis
---

# FFmpeg Audio Processing Skill

Extract, normalize, mix, and process audio tracks from video files.

## When to Use

- Extract audio from video
- Normalize audio levels
- Mix multiple audio tracks
- Convert audio formats
- Extract specific channels
- Adjust audio volume

## Extract Audio

```bash
# Extract as MP3
ffmpeg -i video.mp4 -vn -acodec libmp3lame -q:a 2 audio.mp3

# Extract as AAC (copy, no re-encode)
ffmpeg -i video.mp4 -vn -c:a copy audio.aac

# Extract as WAV (uncompressed)
ffmpeg -i video.mp4 -vn -acodec pcm_s16le audio.wav

# Extract specific audio stream
ffmpeg -i video.mp4 -map 0:a:1 -c:a copy audio2.aac
```

## Normalize Audio

```bash
# Loudness normalize (ITU-R BS.1770-4 / EBU R128) - prefer true-peak headroom for delivery
# Quick (single-pass):
ffmpeg -i input.mp4 -af "loudnorm=I=-23:TP=-2:LRA=11" output.mp4

# Best practice (two-pass) for accurate loudness + fewer overs:
# Pass 1: measure
ffmpeg -i input.mp4 -af "loudnorm=I=-23:TP=-2:LRA=11:print_format=json" -f null -
# Pass 2: apply (fill in measured_* fields from pass 1 output)
ffmpeg -i input.mp4 -af "loudnorm=I=-23:TP=-2:LRA=11:measured_I=...:measured_TP=...:measured_LRA=...:measured_thresh=...:offset=...:linear=true" output.mp4

# Avoid using raw multipliers (e.g., volume=2.0) as "normalization" for speech;
# it can clip and reduce naturalness. If you only need a small gain trim, use dB:
ffmpeg -i input.mp4 -af "volume=+2dB" output.mp4
```

## Volume Adjustment

```bash
# Increase volume by 6dB
ffmpeg -i input.mp4 -af "volume=6dB" output.mp4

# Decrease volume by 3dB
ffmpeg -i input.mp4 -af "volume=-3dB" output.mp4

# Set absolute volume
ffmpeg -i input.mp4 -af "volume=0.5" output.mp4
```

## Channel Operations

```bash
# Extract left channel
ffmpeg -i stereo.mp3 -map_channel 0.0.0 left.mp3

# Extract right channel
ffmpeg -i stereo.mp3 -map_channel 0.0.1 right.mp3

# Convert stereo to mono
ffmpeg -i stereo.mp3 -ac 1 mono.mp3

# Convert mono to stereo
ffmpeg -i mono.mp3 -ac 2 stereo.mp3
```

## Mix Audio Tracks

```bash
# Replace audio track (preserve video, encode audio once)
# -shortest prevents extending past video; -map 0:v keeps original visuals.
ffmpeg -i video.mp4 -i mastered.wav \
  -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -ar 48000 -ac 1 -b:a 192k -shortest output.mp4

# Mix two audio tracks (e.g., original + new) with explicit mapping and audio encode
ffmpeg -i video.mp4 -i audio2.wav \
  -filter_complex "[0:a][1:a]amix=inputs=2:duration=first" \
  -map 0:v:0 -map "[a]" -c:v copy -c:a aac -ar 48000 -ac 1 -b:a 192k -shortest output.mp4

# Mix with volume control (keep processing minimal for speech naturalness)
ffmpeg -i video.mp4 -i bgm.wav \
  -filter_complex "[0:a]volume=1.0[voice];[1:a]volume=0.3[music];[voice][music]amix=inputs=2:duration=first[a]" \
  -map 0:v:0 -map "[a]" -c:v copy -c:a aac -ar 48000 -ac 1 -b:a 192k -shortest output.mp4
```

## Audio Delay

```bash
# Delay audio by 0.5 seconds
ffmpeg -i video.mp4 -itsoffset 0.5 -i video.mp4 \
  -map 0:v -map 1:a -c copy output.mp4

# Using adelay filter (milliseconds)
ffmpeg -i input.mp4 -af "adelay=500|500" output.mp4
```

## Sample Rate Conversion



## Speech / TTS Dubbing (High-Naturalness Mastering)

When preparing TTS or recorded dialog for dubbing, prefer *minimal*, transparent processing. Speech naturalness often degrades from: low-quality resampling, repeated lossy re-encoding, aggressive EQ/compression, clipping, and stacking volume boosts.

### Recommended target format (typical dubbing deliverable)
- **48 kHz**, **mono** (or stereo if required by spec)
- Avoid lossy intermediate exports; keep **WAV/FLAC** until the final mux.

### High-quality resampling to 48 kHz (libsoxr)
Use SoX resampler for transparency:
```bash
ffmpeg -i in.wav -af "aresample=48000:resampler=soxr:precision=28" -ar 48000 out_48k.wav
```

### Safe mono downmix (speech)
For stereo sources, downmix safely (avoid phase cancellation surprises):
```bash
# Simple, safe downmix
ffmpeg -i in.wav -af "pan=mono|c0=0.5*c0+0.5*c1" -ac 1 out_mono.wav
```

### Minimal speech mastering chain (typical)
A good default order is:
1) **High-pass** (remove rumble) → 2) **De-click / short fades** (if needed) → 3) **Resample** → 4) **Loudnorm (once)**

Example (single-pass loudnorm for quick iteration):
```bash
ffmpeg -i tts.wav -af "highpass=f=80,afade=t=in:st=0:d=0.02,afade=t=out:st=0:d=0.02,aresample=48000:resampler=soxr:precision=28,loudnorm=I=-23:TP=-2:LRA=11" -ar 48000 -ac 1 mastered.wav
```

### Loudness normalization best practice: two-pass loudnorm
Two-pass `loudnorm` is more reliable and helps prevent clipping. Use **true-peak headroom** (commonly **TP=-2 dB**) for AAC/MP4 delivery.

Pass 1 (measure):
```bash
ffmpeg -i tts.wav -af "loudnorm=I=-23:TP=-2:LRA=11:print_format=json" -f null -
```
Pass 2 (apply using measured values from pass 1 JSON):
```bash
ffmpeg -i tts.wav -af "loudnorm=I=-23:TP=-2:LRA=11:measured_I=...:measured_TP=...:measured_LRA=...:measured_thresh=...:offset=...:linear=true:print_format=summary" -ar 48000 -ac 1 mastered.wav
```
Notes:
- Run `loudnorm` **once** in the final mastering chain.
- Avoid chaining `volume` after `loudnorm` (it can break compliance and clip).

### Tempo (duration) adjustment limits for speech
If you must fit a speech segment into a time window, keep time-stretch conservative:
- Prefer **0.95–1.05** for best quality
- Avoid going beyond **0.90–1.10** unless absolutely necessary

Example (speed up 3%):
```bash
ffmpeg -i tts.wav -af "atempo=1.03" tts_fitted.wav
```
If you need larger changes, do multiple `atempo` stages (each must be 0.5–2.0), but expect quality loss:
```bash
ffmpeg -i tts.wav -af "atempo=1.1,atempo=1.1" tts_more.wav
```

### Clipping prevention (especially after EQ/volume)
If you must boost, use a limiter rather than raw `volume` stacking:
```bash
ffmpeg -i in.wav -af "alimiter=limit=0.95" out.wav
```

### Quality cautions (common artifact sources)
- Don’t repeatedly re-encode AAC/MP3 during iteration; keep a lossless master.
- Avoid aggressive compression/EQ on TTS unless you hear a clear problem.
- Avoid multiple `volume=...` boosts; target loudness with `loudnorm` instead.

```bash
# Resample to 48kHz
ffmpeg -i input.mp4 -af "aresample=48000" output.mp4

# Resample audio only
ffmpeg -i input.mp4 -vn -af "aresample=48000" -ar 48000 audio.wav
```

## Audio Filters

```bash
# High-pass filter (remove low frequencies)
ffmpeg -i input.mp4 -af "highpass=f=200" output.mp4

# Low-pass filter (remove high frequencies)
ffmpeg -i input.mp4 -af "lowpass=f=3000" output.mp4

# Band-pass filter
ffmpeg -i input.mp4 -af "bandpass=f=1000:width_type=h:w=500" output.mp4

# Fade in/out
ffmpeg -i input.mp4 -af "afade=t=in:st=0:d=2,afade=t=out:st=8:d=2" output.mp4
```

## Audio Analysis

```bash
# Detect volume levels
ffmpeg -i input.mp4 -af "volumedetect" -f null -

# Measure loudness (LUFS)
ffmpeg -i input.mp4 -af "ebur128=peak=true" -f null -

# Get audio statistics
ffprobe -v error -select_streams a:0 \
  -show_entries stream=sample_rate,channels,bit_rate \
  -of json input.mp4
```

## Combine Multiple Audio Files

```bash
# Concatenate audio files
ffmpeg -i "concat:audio1.mp3|audio2.mp3|audio3.mp3" -c copy output.mp3

# Using file list
# file 'audio1.mp3'
# file 'audio2.mp3'
ffmpeg -f concat -safe 0 -i list.txt -c copy output.mp3
```

## Notes

- Use `-vn` to disable video when extracting audio
- `-map` to select specific streams
- `-af` for audio filters
- `-ac` for channel count
- `-ar` for sample rate
- Normalization may require two passes for accurate results (recommended for `loudnorm`).
- For speech/TTS, prioritize transparency: high-quality resampling (`libsoxr`), minimal EQ/dynamics, avoid clipping, and avoid repeated lossy re-encoding.
