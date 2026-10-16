---
name: text-to-speech
description: Produce delivery-ready TTS audio by selecting a viable engine, cleaning segments, aligning timing, and verifying loudness and output specs.
---

# SKILL: TTS Audio Mastering

Produce clean, consistent, delivery-ready TTS audio for video dubbing: engine selection, segment processing, timing, loudness, and export specs.

## Choose an engine (quality + reliability)

Prefer a ranked fallback strategy so you don’t silently degrade quality.

1. **Offline neural TTS** (preferred): deterministic and network-free.
2. **Cloud neural TTS**: only if network/auth is known to work.
3. **Formant TTS** (e.g., espeak): last resort; if “human-level” quality is required, stop and switch engines/models instead of proceeding.

```bash
# Quick viability checks (examples)
command -v piper || true
command -v espeak-ng || true
python -c "import shutil; print('has_cloud_cli', bool(shutil.which('edge-tts')))"
```

Decision rule: if the deliverable is judged on naturalness and only formant TTS is available, treat it as a blocker and look for an offline neural model before rendering the final video.

## Segment cleanup (simple, repeatable)

Apply lightweight cleanup consistently across segments.

```bash
# High-pass + gentle low-pass + short fades
ffmpeg -i segment_in.ext -af "highpass=f=20,lowpass=f=16000,afade=t=in:st=0:d=0.05,afade=t=out:st=0:d=0.05" segment_out.wav
```

## Timing: honor windows explicitly

For windowed dubbing, decide a policy for windows that exceed available media and keep media + report consistent.

```bash
# Pad a short segment to a target length (seconds)
ffmpeg -i segment_in.wav -af "apad=pad_dur=1.0" -t 1.0 segment_padded.wav
```

Read references/window-overrun-policy.md when a required segment/window extends past the source duration.
Skip when all windows lie within the source duration.

## Loudness normalization and reporting

Measure after all edits; normalize; then re-measure the **final** waveform.

```bash
ffmpeg -i final_mix.wav -af "ebur128=peak=true" -f null -
ffmpeg -i final_mix.wav -af "loudnorm=I=-23:TP=-1.5:LRA=11" final_norm.wav
ffmpeg -i final_norm.wav -af "ebur128=peak=true" -f null -
```

Read references/ffmpeg-loudness-version-branch.md when `loudnorm` options vary by FFmpeg version or you must report measured LUFS.
Skip when loudness is not graded.

## Post-write verification (don’t ship on assumptions)

```bash
# Verify sample rate, channels, duration, codec on the final deliverable
ffprobe -v error -select_streams a:0 -show_entries stream=codec_name,sample_rate,channels,channel_layout -of json output_video.ext
```

Decision rule: if any required field is ambiguous (codec/container acceptance, loudness target, window policy), re-check the spec and regenerate rather than guessing.

## Common pitfalls

- Proceeding after a cloud TTS failure by silently falling back to low-quality speech.
- Measuring loudness on an intermediate file and reporting it for a different final file.
- Clamping timing windows without making the report fields consistent with the chosen policy.
