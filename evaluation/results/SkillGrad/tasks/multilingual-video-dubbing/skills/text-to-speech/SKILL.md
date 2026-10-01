---
name: text-to-speech
description: Produce delivery-ready TTS segments for video pipelines, including resampling, loudness normalization, and a mandatory pre-termination deliverables gate.
---

# SKILL: TTS Audio Mastering

Produce clean, delivery-ready TTS audio for video pipelines: segment creation, cleanup, loudness normalization, alignment, export specs, and pre-termination deliverables verification.

## Plan the Output Deliverables (before processing)

1. Enumerate required artifacts (exact paths + formats) and keep as a checklist.
2. Create parent directories for required output paths early.
3. Persist the chosen deliverable set: later prompt language is metadata unless required paths/formats change.

## Pre-termination Deliverables Hook (do this right before end_turn)

Immediately before termination, run the deliverables gate unconditionally: verify all required artifacts exist at exact paths and are minimally readable; if any check fails, return to the producer step and re-check until it passes.

```bash
mkdir -p /outputs /outputs/tts_segments
ls -la /outputs /outputs/tts_segments
ffprobe -v error -show_streams -show_format /outputs/tts_segments/seg_0.wav >/dev/null
ffprobe -v error -show_streams -show_format /outputs/dubbed.mp4 >/dev/null
python - <<'PY'
import json
json.load(open('/outputs/report.json','r',encoding='utf-8'))
print('report: ok')
PY
```

Decision rule: do not end the run until the hook passes.

Read references/deliverables-gate.md when the grader checks for files at exact paths under /outputs. Skip when the caller collects outputs from stdout only.

## TTS Engine & Output Basics

Confirm the native sample rate and channel count of synthesized audio before resampling for delivery.

```bash
ffprobe -v error -select_streams a:0 -show_entries stream=sample_rate,channels -of default=nw=1:nk=1 tts_segment.wav
```

## Speech Cleanup (per segment)

Apply lightweight, consistent processing and short fades to prevent clicks.

```bash
ffmpeg -y -i tts_segment.wav \
  -af "highpass=f=20,lowpass=f=16000,afade=t=in:d=0.05,afade=t=out:d=0.05" \
  cleaned.wav
```

## Loudness Normalization

Normalize after cleanup and timing edits; if you change tempo/duration later, re-normalize.

```bash
ffmpeg -y -i cleaned.wav -af "loudnorm=I=-23:TP=-1.5:LRA=11" normalized.wav
```

## Timing & Segment Boundary Handling

Pad short segments with silence; handle long segments via gentle tempo change or careful trimming; apply fades after padding/trimming.

```bash
ffmpeg -y -i normalized.wav -ac 1 -ar 48000 -af "apad" -t 5.0 seg.wav
```

## Common Pitfalls

- Treating “done with processing” as “done with the task”; file-based graders require writing artifacts to the exact `/outputs/...` paths and verifying readability.
