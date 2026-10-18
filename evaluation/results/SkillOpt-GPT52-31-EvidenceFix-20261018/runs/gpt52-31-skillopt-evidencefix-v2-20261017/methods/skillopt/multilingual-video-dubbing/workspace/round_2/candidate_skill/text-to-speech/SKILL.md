---

name: text-to-speech
description: "Practical mastering steps for TTS audio: cleanup, loudness normalization, alignment, and delivery specs."
---

# SKILL: TTS Audio Mastering

This skill focuses on producing clean, consistent, and delivery-ready TTS audio for video tasks. It covers speech cleanup, loudness normalization, segment boundaries, and export specs.

## 1. TTS Engine & Output Basics

Choose a TTS engine based on deployment constraints and quality needs:

* **Modern neural multilingual TTS** (preferred): use high-MOS neural engines with strong target-language support and expressive prosody.
  * Cloud options: Edge-TTS neural voices, OpenAI TTS, Azure Neural, Google/Polly neural.
  * Offline/local options: Kokoro or other current neural checkpoints compatible with the runtime.
* **Fallback rule:** if a preferred engine fails because of Python/package/runtime mismatch, switch to another neural engine that works in the environment rather than falling back to formant synthesis.
* **Formant TTS** (e.g., espeak-ng): acceptable for debugging/alignment only; avoid for final delivery because MOS/UTMOS is usually poor.

Voice selection matters more than post-processing. Prefer voices with:
* stable pacing and pitch
* natural pauses around punctuation
* clear consonants without metallic/vocoder artifacts
* native support for the target language/script

Runtime compatibility notes:
* Verify Python and CUDA/CPU compatibility before installing large TTS packages.
* Some TTS packages fail on newer Python versions; keep a backup engine available.
* Network-dependent engines should have an offline-safe fallback workflow.

**Key rule:** Always confirm the **native sample rate** of the generated audio before resampling for video delivery. Keep intermediate renders as WAV/FLAC and resample once at the end.

---

## 2. Speech Cleanup (Per Segment)

Apply lightweight processing to avoid common artifacts:

* **Rumble/DC removal:** high-pass filter around **20 Hz**
* **Harshness control:** optional low-pass around **16 kHz** (helps remove digital fizz)
* **Click/pop prevention:** short fades at boundaries (e.g., **50 ms** fade-in and fade-out)

Recommended FFmpeg pattern (example):

* Add filters in a single chain, and keep them consistent across segments.

---


### Naturalness preservation rules

* Avoid aggressive denoise, hard compression, strong de-essing, clipping, or repeated lossy transcoding; these commonly reduce perceived naturalness and UTMOS.
* Use short boundary fades conservatively (typically 5–20 ms). Long fades on short segments can sound unnatural.
* Normalize loudness after timing edits, not before.
* Prefer transparent resampling for final delivery:

```bash
ffmpeg -y -i in.wav -af "aresample=48000:resampler=soxr:precision=28" -ar 48000 -ac 1 out.wav
```

* Before export, listen for metallic artifacts, robotic pacing, clipped consonants, or unstable pauses. If quality is poor, switch voices/models before adding more DSP.

---

## 3. Loudness Normalization

Target loudness depends on the benchmark/task spec. A common target is ITU-R BS.1770 loudness measurement:

* **Integrated loudness:** **-23 LUFS**
* **True peak:** around **-1.5 dBTP**
* **LRA:** around **11** (optional)

Recommended workflow:

1. **Measure loudness** using FFmpeg `ebur128` (or equivalent meter).
2. **Apply normalization** (e.g., `loudnorm`) as the final step after cleanup and timing edits.
3. If you adjust tempo/duration after normalization, re-normalize again.

---

## 4. Timing & Segment Boundary Handling

When stitching segment-level TTS into a full track:

* Match each segment to its target window as closely as possible.
* If a segment is shorter than its window, pad with silence.
* If a segment is longer, use gentle duration control (small speed change) or truncate carefully.
* Always apply boundary fades after padding/trimming to avoid clicks.

**Sync guideline:** keep end-to-end drift small (e.g., **<= 0.2s**) unless the task states otherwise.


## 5. Multilingual Dubbing Workflow

For subtitle-window dubbing, shape prosody before mastering:

* Split long lines into shorter clauses to create natural breath groups.
* Use punctuation intentionally; commas and periods help neural models create realistic pauses.
* If supported, use light SSML only for modest pacing control:

```xml
<speak>
  こんにちは。<break time="250ms"/>
  次の機能を紹介します。
</speak>
```

Duration fitting priority:
1. Pad silence when speech is shorter than the window.
2. Use gentle tempo adjustment when slightly long/short.
3. Rewrite overly dense text instead of extreme time-stretching.
4. Trim only trailing silence, not phonemes.

Keep tempo changes modest when using `atempo`:

```bash
# Mild 3% speed-up
ffmpeg -y -i seg.wav -af "atempo=1.03" seg_fit.wav
```

Avoid extreme tempo changes (for example >10%) because they often create robotic cadence and reduce MOS/UTMOS.


## 6. Final Validation Checklist

Before muxing into the final MP4:

* Verify output audio is 48 kHz mono.
* Run loudness normalization once at the end of the pipeline.
* Check that segment placement starts match subtitle windows within 10 ms.
* Confirm end drift remains within task tolerance.
* Run a perceptual review on at least one exported segment. If speech still sounds synthetic or buzzy, change the voice or engine rather than stacking more filters.
