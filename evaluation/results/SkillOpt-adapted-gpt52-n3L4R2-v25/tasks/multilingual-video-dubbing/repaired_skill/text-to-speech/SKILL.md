---

name: text-to-speech
description: "Practical mastering steps for TTS audio: cleanup, loudness normalization, alignment, and delivery specs."
---

# SKILL: TTS Audio Mastering

This skill focuses on producing clean, consistent, and delivery-ready TTS audio for video tasks. It covers speech cleanup, loudness normalization, segment boundaries, and export specs.

## 1. TTS Engine & Output Basics

Choose a TTS engine based on deployment constraints and quality needs:

* **Neural offline** (e.g., Kokoro): stable, high quality, no network dependency.
* **Cloud TTS** (e.g., Edge-TTS / OpenAI TTS): convenient, higher naturalness but network-dependent.
* **Formant TTS** (e.g., espeak-ng): for prototyping only; often less natural.

**Key rule:** Always confirm the **native sample rate** of the generated audio before resampling for video delivery.

---

## 2. Speech Cleanup (Per Segment)

Apply lightweight processing to avoid common artifacts:

* **Rumble/DC removal:** high-pass filter around **20 Hz**
* **Harshness control:** optional low-pass around **16 kHz** (helps remove digital fizz)
* **Click/pop prevention:** short fades at boundaries (e.g., **50 ms** fade-in and fade-out)

Recommended FFmpeg pattern (example):

* Add filters in a single chain, and keep them consistent across segments.

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

For multilingual dubbing, treat `/root/segments.srt` as the authoritative placement timeline. Parse SRT timestamps exactly (accept both comma and period millisecond separators), retain integer `start_ms` and `end_ms`, and compute `window_duration_ms = end_ms - start_ms` without rounding. Parse `/root/source_text.srt` and `/root/reference_target_text.srt` with the same parser and pair cues one-to-one by stable subtitle index/order; fail rather than silently dropping, duplicating, or inventing a cue when the counts or indices do not match.

Synthesize every paired target cue independently and preserve stable cue order. Measure **raw speech duration before adding silence padding, fades, placement, loudness processing, or resampling**. Fit that speech to its assigned window in this order:

1. Use a conservative, bounded speaking-rate adjustment or time-stretch first, then remeasure. Chain bounded tempo factors when needed rather than applying an extreme single factor.
2. If the speech is shorter than the window, preserve it and append silence to the window boundary.
3. Trim only as a last resort if the bounded adjustment still cannot fit the window.

Record the control actually used for each cue as exactly one of `rate_adjust`, `pad_silence`, or `trim`; do not report a planned control if the rendered result used another one. Keep each fitted cue within its assigned window. Apply short fades only after timing edits, and ensure fades do not change the reported placement boundaries. Resampling, cleanup, normalization, and fades must likewise leave the recorded window start/end and placement calculations unchanged.

Create one mono WAV per cue in `/outputs/tts_segments/`, named in stable index order (`seg_0.wav`, `seg_1.wav`, ...). `seg_0.wav` is the required first-cue artifact, not the complete program timeline. Store the complete assembled timeline separately (for example, `/outputs/tts_segments/assembled_timeline.wav`) with silence outside cue windows, using the integer millisecond offsets from `segments.srt` rather than concatenating clips. The assembled timeline is the audio to normalize and mux; retain the individual cue files for artifact and duration verification.

For every cue, report the measured raw/fitted `tts_duration_sec`, `window_start_sec`, `window_end_sec`, actual rendered `placed_start_sec`, `placed_end_sec`, and `drift_sec = placed_end_sec - window_end_sec`. Verify `abs(placed_start_sec - window_start_sec) <= 0.010` seconds and `abs(drift_sec) <= 0.2` seconds before delivery. Render the final assembled audio at 48000 Hz, mono, and measure/normalize it using an ITU-R BS.1770-compatible method after timing edits.



## 5. Multilingual Input, Voice, and Delivery Contract

Read `/root/target_language.txt` deterministically: use its first non-empty, trimmed line as the target-language specification, normalize it to a language code for reporting, and do not substitute a guessed language. Select a voice that explicitly supports that target language. Prefer an installed offline-capable neural voice; if the preferred engine or voice is unavailable, use an installed offline fallback such as `espeak-ng` with the closest verified target-language voice and record the fallback choice. Never silently synthesize in the source language.

Use the target text from `/root/reference_target_text.srt` verbatim after parsing; use `/root/source_text.srt` only for source-text pairing and reporting. Preserve cue text and indices, and fail if any required input is missing or pairing is ambiguous. Inspect the generated WAVs and the separately assembled timeline with media metadata tools before writing outputs.

The complete normalized assembled timeline, not `/outputs/tts_segments/seg_0.wav` unless there is only one cue, must be used to create `/outputs/dubbed.mp4` while preserving the original visual stream. The final audio must be 48000 Hz and mono. Write `/outputs/report.json` only after validation, using language codes and including the actual measured loudness, original and final durations, audio properties, every paired cue's source/target text, placement boundaries, drift, measured TTS duration, and its actual `duration_control`. Keep the complete timeline artifact separate from the required first-segment artifact and make this distinction explicit in any internal metadata or report.
