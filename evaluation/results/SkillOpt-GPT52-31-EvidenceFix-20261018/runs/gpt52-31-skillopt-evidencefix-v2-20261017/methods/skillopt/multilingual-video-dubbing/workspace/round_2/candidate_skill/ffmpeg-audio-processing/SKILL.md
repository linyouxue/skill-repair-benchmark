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

## Normalize Audio (Speech / Dubbing)

For dubbing, prefer **EBU R128 / ITU-R BS.1770-4 loudness normalization** with **true-peak headroom** and *avoid “volume=2.0” style boosting* (often clips and harms naturalness).

```bash
# Loudness normalize (quick single-pass, good for iteration)
# TP=-2 dB is a common safer choice before AAC encoding.
ffmpeg -i input.wav -af "loudnorm=I=-23:TP=-2:LRA=11" -ar 48000 -ac 1 output_norm.wav

# Best practice: two-pass loudnorm (carry measured values into pass 2)
# Pass 1: measure (copy the JSON fields)
ffmpeg -i input.wav -af "loudnorm=I=-23:TP=-2:LRA=11:print_format=json" -f null -

# Pass 2: apply using measured_* and offset from pass 1 JSON
ffmpeg -y -i input.wav -af "loudnorm=I=-23:TP=-2:LRA=11:measured_I=...:measured_TP=...:measured_LRA=...:measured_thresh=...:offset=...:linear=true" \
  -ar 48000 -ac 1 output_norm.wav

# If you only need a small trim, use dB (less risk than big multipliers)
ffmpeg -i input.wav -af "volume=+2dB" output_trim.wav
```

**Clipping/headroom guidance (important for MOS):**
- Keep peaks below 0 dBFS at all times; leave **~1–2 dBTP** headroom for AAC/MP4.
- Prefer `loudnorm` (with TP headroom) over stacking multiple `volume` filters.
- If you must hard-stop peaks, use a gentle limiter as a last resort:

```bash
ffmpeg -i input.wav -af "alimiter=limit=0.98" limited.wav
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

## Mix / Replace Audio Tracks (robust mux for dubbing)

Prefer feeding FFmpeg a **mastered 48kHz mono WAV** and encode AAC once at the end.

```bash
# Replace audio track (preserve video stream, encode compliant AAC audio)
ffmpeg -y -i video.mp4 -i mastered_48k_mono.wav \
  -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 192k -ar 48000 -ac 1 \
  -movflags +faststart -shortest output.mp4

# Mix original audio + dubbed audio (duck original lightly; keep speech dominant)
ffmpeg -y -i video.mp4 -i dubbed.wav \
  -filter_complex "[0:a]volume=0.25[orig];[1:a]volume=1.0[dub];[orig][dub]amix=inputs=2:duration=first:normalize=0[m]" \
  -map 0:v:0 -map "[m]" -c:v copy -c:a aac -b:a 192k -ar 48000 -ac 1 \
  -movflags +faststart -shortest output.mp4

# Replace audio but guarantee exact program length (avoid drift)
# Use known duration (seconds) and trim the audio to match.
ffmpeg -y -i video.mp4 -i mastered.wav \
  -filter_complex "[1:a]aresample=48000:resampler=soxr:precision=28,pan=mono|c0=c0,atrim=0:12.052[a]" \
  -map 0:v:0 -map "[a]" -c:v copy -c:a aac -b:a 192k -ar 48000 -ac 1 \
  -movflags +faststart output.mp4
```

Notes:
- Use `-shortest` when the audio should never extend past video.
- Avoid repeated AAC encode/decode during iteration; keep a WAV master until final mux.


## Audio Delay

```bash
# Delay audio by 0.5 seconds
ffmpeg -i video.mp4 -itsoffset 0.5 -i video.mp4 \
  -map 0:v -map 1:a -c copy output.mp4

# Using adelay filter (milliseconds)
ffmpeg -i input.mp4 -af "adelay=500|500" output.mp4
```

## Sample Rate Conversion



## Speech / TTS Dubbing Mastering (MOS-preserving recipes)

### Target delivery (typical dubbing)
- **48 kHz**, **mono**, keep intermediates **WAV/FLAC** (avoid repeated AAC/MP3 re-encodes).

### High-quality 48 kHz mono conversion (transparent)
Use `soxr` for best resampling quality and do a safe mono downmix.

```bash
# Transparent resample + mono downmix
ffmpeg -y -i in.wav \
  -af "pan=mono|c0=0.5*c0+0.5*c1,aresample=48000:resampler=soxr:precision=28" \
  -ar 48000 -ac 1 out_48k_mono.wav
```

### Gentle cleanup chain (artifact-safe)
Keep processing minimal; heavy denoise/compression often reduces naturalness.

```bash
# Typical light cleanup: rumble cut + optional lowpass + micro-fades to avoid clicks
ffmpeg -y -i in.wav \
  -af "highpass=f=80,lowpass=f=16000,afade=t=in:st=0:d=0.01,afade=t=out:st=0:d=0.01" \
  cleaned.wav
```

### Duration fitting for speech (conservative)
- Prefer **silence padding** over aggressive time-stretch.
- If stretching is required, keep within about **0.95–1.08** when possible (avoid robotic artifacts).

```bash
# Small tempo change (3% faster)
ffmpeg -y -i in.wav -af "atempo=1.03" faster.wav

# If TTS is shorter than the window: pad with silence to target duration (seconds)
ffmpeg -y -i in.wav -af "apad=pad_dur=1.60" -t 1.60 padded.wav

# If TTS is slightly longer: trim to window end (avoid cutting phonemes; trim trailing silence if possible)
ffmpeg -y -i in.wav -af "atrim=0:1.60" trimmed.wav
```

### Sample-accurate placement / alignment (adelay + apad + atrim)
Place a segment at an exact start time (ms), then limit total length.

```bash
# Place segment starting at 500ms, then pad to ensure mix works, then trim final length
ffmpeg -y -i seg.wav \
  -af "adelay=500|500,apad" placed.wav

# When building a full-length track, trim to the exact program duration
ffmpeg -y -i placed.wav -af "atrim=0:12.052" full_len.wav
```

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



## Quality Audit & Troubleshooting (dubbing)

### Loudness / compliance checks
```bash
# Integrated loudness + true peak (quick audit)
ffmpeg -i out.wav -af "ebur128=peak=true" -f null -

# Stats for clipping / DC offset / silence
ffmpeg -i out.wav -af "astats=metadata=1:reset=1" -f null -
```

### Common failures and fixes
- **"Clipping" / harsh distortion**: remove extra `volume` boosts; re-run two-pass `loudnorm` with TP headroom (e.g., TP=-2). Consider gentle `alimiter` only if needed.
- **Robotic/metallic sound (low MOS/UTMOS)**: reduce DSP (especially heavy denoise/EQ), avoid big `atempo` changes, keep resampling high quality (`soxr`), and avoid multiple lossy re-encodes.
- **Clicks at segment boundaries**: add **micro-fades** (5–20 ms) after trimming/padding; ensure cuts occur on zero crossings when possible.
- **Sync drift**: prefer `adelay` for start alignment and `atrim` to exact end; avoid forcing large time-stretch to hit end time.
- **"Non-monotonous DTS" / mux warnings**: keep `-c:v copy`, ensure audio is CFR-aligned via `-shortest` and/or explicit `atrim`, and avoid mixing multiple sources without `apad`.

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
- Normalization may require two passes for accurate results
