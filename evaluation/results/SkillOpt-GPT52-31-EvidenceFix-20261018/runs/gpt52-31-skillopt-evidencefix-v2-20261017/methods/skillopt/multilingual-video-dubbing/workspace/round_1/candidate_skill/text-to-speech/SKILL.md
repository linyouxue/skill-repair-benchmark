---

name: text-to-speech
description: "Practical mastering steps for TTS audio: cleanup, loudness normalization, alignment, and delivery specs."
---

# SKILL: TTS Audio Mastering

This skill focuses on producing clean, consistent, and delivery-ready TTS audio for video tasks. It covers speech cleanup, loudness normalization, segment boundaries, and export specs.

## 1. TTS Engine, Voice Selection, and Multilingual Quality (UTMOS-first)

Naturalness is primarily determined at **synthesis time**. Mastering cannot “fix” robotic prosody. For multilingual dubbing tasks scored by MOS/UTMOS, prioritize **modern neural multilingual** TTS and pick voices that already sound human.

### 1.1 Engine choice (quality-first)

Prefer engines/voices with strong multilingual prosody modeling:

* **High-quality cloud neural TTS** (recommended when allowed): e.g., Azure Neural voices, Google/Polly neural, OpenAI TTS, Edge-TTS neural voices.
* **High-quality local neural TTS** (recommended when offline/no-network): use current neural models that support the **target language** with natural prosody.
* **Formant TTS (espeak-ng, etc.)**: **avoid for final output**; acceptable only for prototyping/alignment.

**Rule:** do not ship formant/fallback audio if a MOS/UTMOS gate exists.

### 1.2 Voice selection criteria (what to test quickly)

Pick a voice that, on a short sample, has:

* clear consonants without “buzzy”/metallic harmonics
* stable pitch (no random pitch jumps)
* natural pauses at commas and sentence ends
* no aggressive noise suppression artifacts (musical noise) and no vocoder “fizz”

If multiple voices exist for the target language, synthesize a 5–10s excerpt and choose the one that sounds most natural **before** doing any mastering.

### 1.3 Generate at native sample rate; convert transparently

**Key rule:** generate TTS at the engine’s **native sample rate** and bit depth. Only then convert for delivery (typically **48 kHz mono** for video).

Transparent resample to 48 kHz mono (avoid extra DSP):

```bash
ffmpeg -y -i in_tts.wav -ac 1 -ar 48000 -af aresample=resampler=soxr:precision=28 out_48k_mono.wav
```

Avoid repeated resampling or repeated lossy encoding. Keep intermediate files as WAV/FLAC.

---

## 2. Speech Cleanup (Per Segment)

Apply lightweight processing to avoid common artifacts:

* **Rumble/DC removal:** high-pass filter around **20 Hz**
* **Harshness control:** optional low-pass around **16 kHz** (helps remove digital fizz)
* **Click/pop prevention:** short fades at boundaries (e.g., **50 ms** fade-in and fade-out)

Recommended FFmpeg pattern (example):

* Add filters in a single chain, and keep them consistent across segments.

---

### 2.1 Anti-artifact rules (preserve naturalness)

* **Do not over-process**: heavy denoise, aggressive de-essing, strong compression, or hard limiting often reduces MOS.
* **Avoid clipping at every stage**: leave headroom (e.g., peaks below -3 dBFS pre-normalization).
* **Minimize normalization passes**: do cleanup/timing first, then do loudness normalization once at the end (two-pass is fine).
* **Use micro-fades** at every cut/pad boundary (5–20 ms is usually sufficient; 50 ms can sound like unnatural “ducking” on short segments).
* **De-click only when needed** (for boundary clicks). If clicks persist, fix edit points and fades first.

Speech-preserving FFmpeg chain example (gentle):

```bash
ffmpeg -y -i seg.wav -af "highpass=f=20,lowpass=f=16000,afade=t=in:st=0:d=0.01,afade=t=out:st=END-0.01:d=0.01" cleaned.wav
```

(Replace `END` by segment duration when scripting; or apply fades after concatenation.)

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


## 5. Prosody & Duration Fitting for Subtitle Windows (dubbing workflow)

To improve naturalness (and UTMOS), control **prosody** and **pacing** *before* mastering.

### 5.1 Text shaping (language-aware)

* **Chunk long lines** into 1–2 short sentences (natural breath groups). Prefer splitting on punctuation.
* Use punctuation to drive pauses: commas/semicolons create short pauses; periods create longer pauses.
* Avoid ALL CAPS, excessive ellipses, or repeated punctuation that can trigger odd prosody.

If the engine supports **SSML**, use it sparingly:

* `<break time="150ms"/>` for comma-like pauses
* `<break time="250-400ms"/>` for sentence boundaries
* modest speaking-rate changes (e.g., 0.95–1.08), avoiding extremes

SSML pacing example:

```xml
<speak>
  こんにちは。<break time="300ms"/>
  今日は新しい機能を紹介します。<break time="200ms"/>
  はじめましょう。
</speak>
```

### 5.2 Safe duration control (avoid time-stretch artifacts)

When fitting speech into a window, prioritize strategies in this order:

1. **Pad silence** (preferred): if TTS is shorter, pad at end (or distribute small pauses between clauses).
2. **Small tempo adjustment** (acceptable): if slightly long/short, adjust speed gently.
   * keep rate within ~**0.95–1.08** when possible
   * avoid aggressive stretching/compression; it sounds robotic and hurts MOS
3. **Text revision** (best for large mismatch): shorten/lengthen wording rather than heavy DSP.
4. **Trim** only as a last resort and only trailing silence—avoid cutting phonemes.

Tempo adjust with FFmpeg `atempo` (keep within 0.5–2.0 per filter; chain if needed):

```bash
# 3% faster
ffmpeg -y -i seg.wav -af "atempo=1.03" seg_fitted.wav
```

Padding to a target duration `T` (seconds) without stretching:

```bash
ffmpeg -y -i seg.wav -af "apad=pad_dur=T" -t T seg_padded.wav
```

### 5.3 Segment placement rules (for strict alignment tests)

* Place each segment with **sample-accurate start** at `window_start` (<=10 ms error).
* Compute drift as `placed_end - window_end`; keep `|drift| <= 0.2s`.
* Prefer keeping speech natural and using **silence padding** to fill windows rather than forcing perfect end alignment via heavy time-stretch.


## 6. Perceptual Validation (MOS/UTMOS-oriented)

Before final export, run a quick iterative check:

1. **Listen** to each segment for: metallic “vocoder” fizz, unnatural pauses, clipped consonants, and overly fast/slow cadence.
2. Check **peak headroom** pre-normalization (avoid clipping).
3. Confirm final delivery specs: **48 kHz**, **mono**, and loudness normalized (e.g., **-23 LUFS**, **~ -1.5 dBTP**).
4. If a MOS/UTMOS gate exists and score is low:
   * switch voice/model first (largest impact)
   * reduce DSP (denoise/limiting) next
   * revise text chunking/punctuation/SSML for more natural prosody

Two-pass loudness normalization (end of pipeline):

```bash
# Pass 1 (measure)
ffmpeg -i in.wav -af loudnorm=I=-23:TP=-1.5:LRA=11:print_format=json -f null -

# Pass 2 (apply using measured values from pass 1)
ffmpeg -y -i in.wav -af "loudnorm=I=-23:TP=-1.5:LRA=11:measured_I=...:measured_TP=...:measured_LRA=...:measured_thresh=...:offset=...:linear=true" out_norm.wav
```

Export recommendation: keep intermediates as WAV; encode to AAC only at the final mux into MP4.
