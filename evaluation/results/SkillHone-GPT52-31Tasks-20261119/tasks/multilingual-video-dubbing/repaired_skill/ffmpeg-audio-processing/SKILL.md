---
name: ffmpeg-audio-processing
description: Extract, normalize, mix, and process audio tracks - audio manipulation and analysis
---

# FFmpeg Audio Processing Skill

Extract, normalize, mix, and process audio tracks from video files.

## When to Use

- Extract audio from video
- Normalize audio levels (LUFS / peak)
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

### Loudness normalization (ITU‑R BS.1770 / EBU R128)

```bash
# One-pass normalization (simple)
ffmpeg -i input.wav -af "loudnorm=I=-23:TP=-1.5:LRA=11" output.wav
```

#### Two-pass loudnorm (recommended for repeatability)

Some FFmpeg builds do **not** support `loudnorm=...:measure_only=1`.
A compatible approach is:

```bash
# Pass 1: measure (prints JSON to stderr)
ffmpeg -hide_banner -i input.wav \
  -af "loudnorm=I=-23:TP=-1.5:LRA=11:print_format=json" \
  -f null - 2> loudnorm_pass1.log

# Pass 2: apply using measured_* and offset from the JSON
ffmpeg -hide_banner -y -i input.wav \
  -af "loudnorm=I=-23:TP=-1.5:LRA=11:measured_I=<...>:measured_LRA=<...>:measured_TP=<...>:measured_thresh=<...>:offset=<...>:linear=true" \
  output.wav
```

### Simple gain

```bash
ffmpeg -i input.wav -af "volume=2.0" output.wav
```

### Peak normalization via volumedetect

```bash
ffmpeg -i input.wav -af "volumedetect" -f null -
# Then apply a gain based on detected max_volume
ffmpeg -i input.wav -af "volume=0.5" output.wav
```

## Volume Adjustment

```bash
# Increase volume by 6dB
ffmpeg -i input.wav -af "volume=6dB" output.wav

# Decrease volume by 3dB
ffmpeg -i input.wav -af "volume=-3dB" output.wav

# Set absolute volume (linear)
ffmpeg -i input.wav -af "volume=0.5" output.wav
```

## Channel Operations

```bash
# Extract left channel
ffmpeg -i stereo.wav -map_channel 0.0.0 left.wav

# Extract right channel
ffmpeg -i stereo.wav -map_channel 0.0.1 right.wav

# Convert stereo to mono
ffmpeg -i stereo.wav -ac 1 mono.wav

# Convert mono to stereo
ffmpeg -i mono.wav -ac 2 stereo.wav
```

## Mix Audio Tracks

```bash
# Replace audio track (keep video)
ffmpeg -i video.mp4 -i audio.wav -c:v copy -map 0:v:0 -map 1:a:0 output.mp4

# Mix two audio tracks
ffmpeg -i voice.wav -i music.wav \
  -filter_complex "[0:a][1:a]amix=inputs=2:duration=first" \
  mixed.wav

# Mix with volume control
ffmpeg -i voice.wav -i music.wav \
  -filter_complex "[0:a]volume=1.0[voice];[1:a]volume=0.3[music];[voice][music]amix=inputs=2:duration=first" \
  mixed.wav
```

## Audio Delay

```bash
# Delay audio by 0.5 seconds using itsoffset
ffmpeg -i video.mp4 -itsoffset 0.5 -i video.mp4 \
  -map 0:v -map 1:a -c copy output.mp4

# Using adelay filter (milliseconds)
ffmpeg -i input.wav -af "adelay=500|500" delayed.wav
```

## Sample Rate Conversion

```bash
# Resample to 48kHz
ffmpeg -i input.wav -af "aresample=48000" -ar 48000 output.wav

# Force 48kHz mono PCM (common dubbing delivery)
ffmpeg -i input.wav -ar 48000 -ac 1 -c:a pcm_s16le output.wav
```

## Audio Filters

```bash
# High-pass filter (remove low frequencies)
ffmpeg -i input.wav -af "highpass=f=20" output.wav

# Low-pass filter (remove high frequencies)
ffmpeg -i input.wav -af "lowpass=f=16000" output.wav

# Fade in/out (avoid clicks at cut points)
ffmpeg -i input.wav -af "afade=t=in:st=0:d=0.05,afade=t=out:st=8:d=0.05" output.wav
```

## Audio Analysis

```bash
# Detect volume levels
ffmpeg -i input.wav -af "volumedetect" -f null -

# Measure loudness (LUFS)
ffmpeg -i input.wav -af "ebur128=peak=true" -f null -

# Get audio statistics
ffprobe -v error -select_streams a:0 \
  -show_entries stream=sample_rate,channels,bit_rate \
  -of json input.wav
```

## Combine Multiple Audio Files

```bash
# Concatenate audio files (same codec)
ffmpeg -i "concat:audio1.wav|audio2.wav|audio3.wav" -c copy output.wav

# Using file list (recommended)
# file 'audio1.wav'
# file 'audio2.wav'
ffmpeg -f concat -safe 0 -i list.txt -c copy output.wav
```

## Notes

- Use `-vn` to disable video when extracting audio
- `-map` selects specific streams
- `-af` applies audio filters
- `-ac` sets channel count; `-ar` sets sample rate
- For loudness-critical tasks, prefer a two-pass workflow and verify with `ebur128`
