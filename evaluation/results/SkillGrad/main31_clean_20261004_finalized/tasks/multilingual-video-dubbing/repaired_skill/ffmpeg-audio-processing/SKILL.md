---
name: ffmpeg-audio-processing
description: Extract, resample, normalize, mix, and measure audio with FFmpeg, using version-safe loudness workflows and final artifact validation.
---

# FFmpeg Audio Processing Skill

Extract, resample, normalize, mix, and analyze audio tracks from media files.

## Plan the pipeline (measure → change → re-measure)

1. Decide the **delivery constraints** first (sample rate, channels, container/codec, loudness target).
2. Measure on the **actual file you will deliver** (not an intermediate).
3. After any timing edit (pad/trim/tempo), **re-measure** loudness.

```bash
# Measure then apply changes, then re-measure
ffmpeg -i input_audio.ext -af "ebur128=peak=true" -f null -
ffmpeg -i input_audio.ext -af "aresample=48000,pan=mono|c0=c0" output_audio.ext
ffmpeg -i output_audio.ext -af "ebur128=peak=true" -f null -
```

## Extract audio

```bash
# Extract as WAV (uncompressed)
ffmpeg -i input_video.ext -vn -c:a pcm_s16le output_audio.wav

# Extract and keep original codec (no re-encode)
ffmpeg -i input_video.ext -vn -c:a copy output_audio.ext

# Extract a specific audio stream
ffmpeg -i input_video.ext -map 0:a:0 -c:a copy output_audio.ext
```

## Resample and channel layout

Prefer explicit resampling and mono downmix (don’t assume defaults).

```bash
# Resample to 48 kHz and downmix to mono deterministically
ffmpeg -i input_audio.ext -af "aresample=48000,pan=mono|c0=0.5*c0+0.5*c1" -c:a pcm_s16le output_audio.wav

# Force channel count only (when downmix formula is not important)
ffmpeg -i input_audio.ext -ar 48000 -ac 1 -c:a pcm_s16le output_audio.wav
```

Decision rule: if graders are strict about waveform properties, deliver PCM (e.g., WAV) until the container/codec requirements are confirmed.

## Loudness normalization (version-safe)

Use a workflow that branches on filter capability and always re-measures the final result.

```bash
# One-pass loudnorm (use when two-pass JSON measurement is not supported)
ffmpeg -i input_audio.ext -af "loudnorm=I=-23:TP=-1.5:LRA=11" -c:a pcm_s16le output_audio.wav

# Independent measurement (authoritative for reporting)
ffmpeg -i output_audio.wav -af "ebur128=peak=true" -f null -
```

Read references/ffmpeg-loudness-version-branch.md when you must report LUFS/TP and the environment’s FFmpeg version is unknown.
Skip when loudness reporting is not required.

## Mix / replace audio in a video

```bash
# Replace video audio with new audio (re-encode audio explicitly)
ffmpeg -i input_video.ext -i input_audio.ext \
  -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -shortest output_video.ext

# Mix two tracks with controlled volumes
ffmpeg -i input_a.ext -i input_b.ext \
  -filter_complex "[0:a]volume=1.0[a];[1:a]volume=0.3[b];[a][b]amix=inputs=2:duration=first" \
  -c:a pcm_s16le output_mix.wav
```

Decision rule: prefer `-shortest` only when it is acceptable to truncate to the shorter stream; otherwise pad the shorter stream first.

## Common pitfalls

- Normalizing and then changing duration/tempo without re-normalizing.
- Assuming AAC-in-MP4 is always accepted; verify container+codec against the deliverable spec.
- Claiming measured LUFS based on parsing logs from a non-measurement run.
