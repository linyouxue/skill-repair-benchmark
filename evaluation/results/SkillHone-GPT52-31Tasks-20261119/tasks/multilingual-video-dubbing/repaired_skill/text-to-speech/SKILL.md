---
name: text-to-speech
description: "Practical mastering steps for TTS audio: cleanup, loudness normalization, alignment, and delivery specs."
---

# SKILL: TTS Audio Mastering

This skill focuses on producing clean, consistent, delivery-ready speech audio for video dubbing tasks: choosing a speech source (TTS engine or fallback), creating per-segment WAVs, controlling duration, loudness normalizing to ITU‑R BS.1770 (LUFS), and exporting to required sample rate/channel layouts.

## 0. Fast decision checklist (avoid robotic speech)

Before building the pipeline, decide how you’ll meet **speech naturalness / “human level”** constraints:

1. **Is outbound network available?**
   - If yes, you may use cloud/neural TTS (Edge TTS, etc.).
   - If no (common in sandboxes), treat cloud TTS as unavailable.

2. **Is an offline neural TTS already installed?** (preferred)
   - Examples: `piper`, RHVoice, Coqui-TTS (`TTS`).

3. **Is there a language-specific higher-quality offline option?**
   - Example: for **Japanese**, `pyopenjtalk` (OpenJTalk) is often **far more natural** than formant engines.

4. **If only formant/basic TTS is available (e.g., `espeak-ng`) and the task demands “human level”**:
   - Expect formant speech to sound robotic.
   - Consider the **human-speech fallback** in §2.2 (reuse original spoken audio) **only when translation/semantic fidelity is not evaluated or the user explicitly allows a placeholder**.

Quick availability checks:

```bash
# CLI engines (prefer offline neural if available)
which piper piper-tts mimic3 rhvoice-test \
  espeak-ng espeak festival flite pico2wave spd-say 2>/dev/null || true

# Optional Python engines
python - <<'PY'
import importlib.util
for m in [
    "pyopenjtalk",  # Japanese offline (OpenJTalk)
    "TTS",          # Coqui-TTS
    "piper", "piper_tts",
    "mimic3_tts",
    "edge_tts",     # neural but network-dependent
]:
    print(m, bool(importlib.util.find_spec(m)))
PY
```

If a chosen engine requires network (Edge-TTS, etc.), confirm connectivity before committing to it.

## 1. Choose a TTS engine (offline-first)

In many sandboxed runtimes, **network access is blocked**. Treat cloud TTS as optional and always have an offline fallback.

Priority order (quality-first, offline-first):

1. **Offline neural TTS (preferred, if already available locally)**: highest quality without network (e.g., `piper`, RHVoice, Coqui-TTS).
2. **Higher-quality offline TTS for the target language** (often available even when neural models aren’t): e.g. **OpenJTalk/`pyopenjtalk` for Japanese**, or MBROLA voices (if installed) for some languages.
3. **Other offline CLI TTS tools** (e.g., `festival`, `flite`): quality varies widely by language/voice.
4. **Formant TTS** (e.g., `espeak-ng`): intelligible but often *not* “human level”. Use only as a last resort.

### Network sanity check (quick)

```bash
python - <<'PY'
import urllib.request
for url in ["https://pypi.org/simple/", "https://github.com/"]:
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            print(url, "status", r.status)
    except Exception as e:
        print(url, "ERROR", type(e).__name__, e)
PY
```

## 2. Generate a raw segment WAV

Prefer producing WAV directly to avoid MP3 re-encode artifacts.

### 2.1 Preferred (if available): offline neural TTS

If an offline neural engine is present (e.g., `piper`, RHVoice), use it and output a WAV.

### 2.1.1 Offline Japanese option: `pyopenjtalk` (OpenJTalk)

If you need Japanese TTS and `pyopenjtalk` is installed, it can produce **more natural** speech than formant engines.

#### 2.1.1.a Don’t assume the dictionary is missing — smoke test first

Some `pyopenjtalk` installs download the OpenJTalk dictionary on first use, while others ship with it or have it pre-cached.

Start with a **quick synthesis smoke test**:

```bash
python - <<'PY'
import array
import wave
try:
    import pyopenjtalk
except Exception as e:
    raise SystemExit(f"pyopenjtalk import failed: {e}")

x, sr = pyopenjtalk.tts("テストです。")
print("ok sr=", sr, "sec=", len(x)/sr)

pcm = array.array('h')
for s in x:
    s = max(-1.0, min(1.0, float(s)))
    pcm.append(int(round(s * 32767.0)))

with wave.open('raw.wav', 'wb') as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(sr)
    w.writeframes(pcm.tobytes())

print("wrote raw.wav")
PY
```

If this succeeds, proceed to mastering (§3–§6). If it fails with a dictionary error, use the next step.

#### 2.1.1.b If dictionary lookup fails: locate a cached dictionary directory

If `pyopenjtalk` cannot find the dictionary in a network-blocked environment, look for a cached `open_jtalk_dic_utf_8-*` directory in common locations:

```bash
python - <<'PY'
from pathlib import Path
import site

cands = []
home = Path.home()

# Common cache/share locations
for base in [
    home / '.local' / 'share',
    home / '.cache',
]:
    if base.exists():
        cands += [p for p in base.rglob('open_jtalk_dic_utf_8*') if p.is_dir()]

# Sometimes dictionaries are vendored inside site-packages
for sp in list(site.getsitepackages()) + [site.getusersitepackages()]:
    p = Path(sp)
    if p.exists():
        cands += [q for q in p.rglob('open_jtalk_dic_utf_8*') if q.is_dir()]

cands = sorted({c.resolve() for c in cands})
print('Found', len(cands), 'candidate dict dirs')
for d in cands[:20]:
    print(' ', d)

if cands:
    d = cands[0]
    print('\nTry setting one of these (exact variable name can differ by build):')
    print('  export OPEN_JTALK_DICT_DIR="%s"' % d)
    print('  export OPENJTALK_DICT_DIR="%s"' % d)
PY
```

Then rerun the smoke test.

#### 2.1.1.c Optional: try alternate OpenJTalk voice models (if present)

If your environment contains `.htsvoice` files, using a better voice can noticeably improve naturalness:

```bash
# Look for installed OpenJTalk voice models
python - <<'PY'
from pathlib import Path
import site
roots = [Path.home(), Path('/usr/share'), Path('/usr/local/share')]
for sp in list(site.getsitepackages()) + [site.getusersitepackages()]:
    roots.append(Path(sp))

seen = set()
for r in roots:
    if not r.exists():
        continue
    for p in r.rglob('*.htsvoice'):
        rp = str(p.resolve())
        if rp not in seen:
            seen.add(rp)

print('Found', len(seen), '.htsvoice files')
for p in sorted(seen)[:30]:
    print(' ', p)
PY
```

If `pyopenjtalk.tts` exposes a `voice=` (or similar) argument (check with `inspect.signature`), pass the preferred voice path at synthesis time.

### 2.2 Fallback for “human level” naturalness: reuse original speech audio (only when allowed)

When no high-quality offline TTS is available and network/cloud TTS is blocked, one practical fallback is to **reuse original human speech audio** (or a lightly processed extract) instead of robotic TTS.

Only do this when the user/task allows a **placeholder** (i.e., translation/semantic fidelity is not evaluated) — this improves naturalness but does *not* create translated speech.

Typical approach:

1. Extract the speech window from the source video audio.
2. Convert to the delivery spec (e.g., 48 kHz mono) and apply gentle cleanup.
3. Loudness-normalize to the required LUFS target.

Example (single segment window; substitute your window start/end):

```bash
# 1) Extract the window audio from the source video
ffmpeg -hide_banner -y -ss <WINDOW_START_SEC> -to <WINDOW_END_SEC> -i input.mp4 \
  -vn -ac 1 -ar 48000 -c:a pcm_s16le extracted.wav

# 2) Gentle cleanup (avoid making speech sound "processed")
ffmpeg -hide_banner -y -i extracted.wav \
  -af "highpass=f=20,lowpass=f=16000,afade=t=in:st=0:d=0.02,afade=t=out:st=<FADE_OUT_START>:d=0.02" \
  cleaned.wav

# 3) Loudness normalize (see §5 for two-pass)
ffmpeg -hide_banner -y -i cleaned.wav -af "loudnorm=I=-23:TP=-1.5:LRA=11" normalized.wav
```

### 2.3 Formant TTS example (espeak-ng) — last resort

Use only if you cannot reuse original speech and no better offline engine is available:

```bash
# Raw TTS WAV (voice/lang and speed are engine-dependent)
espeak-ng -v <voice_or_lang> -s <wpm> -w raw.wav --stdin <<'TXT'
<target text goes here>
TXT
```

If your engine outputs MP3/OGG, convert once to a PCM WAV before further processing:

```bash
ffmpeg -hide_banner -y -i raw.mp3 -c:a pcm_s16le raw.wav
```

### 2.4 Improve perceived naturalness (especially for basic TTS)

If you have a **neural/offline** engine available (e.g., `piper`, `mimic3`, RHVoice), use it first: it is usually the easiest way to meet “human level” expectations.

If you are forced to use a more robotic engine (e.g., `espeak-ng`, `festival`, `flite`), you can still improve perceived naturalness:

- **Pick a better voice/variant** for the target language.
- **Tune prosody at synthesis time** (preferred) instead of heavy post-processing:
  - adjust speaking rate (too fast sounds robotic)
  - adjust pitch (avoid extremes)
  - add small pauses (punctuation / word-gap options)
- **Clean the input text**:
  - strip SRT indices and timestamps
  - keep sentences short; add punctuation/line breaks where appropriate
  - normalize numbers/abbreviations if the engine misreads them
- **Keep audio processing gentle**: avoid large time-stretch, harsh EQ, or aggressive limiting.

Optional: if your synthesizer adds noticeable **leading silence**, remove it before alignment and then pad explicitly to the window start:

```bash
# Remove leading/trailing silence conservatively (tune thresholds per material)
ffmpeg -hide_banner -y -i raw.wav \
  -af "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05:stop_periods=1:stop_threshold=-45dB:stop_silence=0.10" \
  raw_trimmed.wav
```

## 3. Resample / downmix to delivery spec early (when required)

Many dubbing pipelines require **48 kHz mono**. Convert early so all downstream timing math is on the final sample grid.

```bash
ffmpeg -hide_banner -y -i raw.wav -ar 48000 -ac 1 -c:a pcm_s16le tts_48k_mono.wav
```

Verify:

```bash
ffprobe -v error -select_streams a:0 \
  -show_entries stream=sample_rate,channels \
  -of default=noprint_wrappers=1 tts_48k_mono.wav
```

## 4. Cleanup to prevent clicks / harshness

Typical light chain:

- `highpass` to remove rumble/DC
- optional `lowpass` to tame harshness
- short fades at boundaries

Example filter chain (set `FADE_OUT_START = duration - fade_sec`):

```bash
# Keep lowpass below Nyquist (sample_rate/2). For 48 kHz audio, 16 kHz is safe.
# If your source audio is 22.05 kHz, use <= 10 kHz.
ffmpeg -hide_banner -y -i tts_48k_mono.wav \
  -af "highpass=f=20,lowpass=f=16000,afade=t=in:st=0:d=0.05,afade=t=out:st=<FADE_OUT_START>:d=0.05" \
  cleaned.wav
```

## 5. Loudness normalization (ITU‑R BS.1770 / LUFS)

When a task asks for BS.1770 compliance, use `loudnorm` (EBU R128/BS.1770) targeting the required integrated loudness (often **-23 LUFS**) and true peak.

### Recommended: two-pass loudnorm (robust across FFmpeg builds)

Some FFmpeg builds do **not** support the `measure_only` option on `loudnorm`. A compatible approach is:

**Pass 1 (measure and get JSON printed to stderr):**

```bash
ffmpeg -hide_banner -i cleaned.wav \
  -af "loudnorm=I=-23:TP=-1.5:LRA=11:print_format=json" \
  -f null - 2> loudnorm_pass1.log
```

Parse the JSON block from `loudnorm_pass1.log` and feed the `measured_*` fields into pass 2.

**Pass 2 (apply normalization):**

```bash
ffmpeg -hide_banner -y -i cleaned.wav \
  -af "loudnorm=I=-23:TP=-1.5:LRA=11:measured_I=<...>:measured_LRA=<...>:measured_TP=<...>:measured_thresh=<...>:offset=<...>:linear=true" \
  normalized.wav
```

### Quick alternative: one-pass loudnorm

```bash
ffmpeg -hide_banner -y -i cleaned.wav -af "loudnorm=I=-23:TP=-1.5:LRA=11" normalized.wav
```

### Verify loudness after normalization

```bash
ffmpeg -hide_banner -i normalized.wav -af "ebur128=peak=true" -f null -
```

## 6. Match a segment to a timing window (pad / trim / rate-adjust)

Given a segment audio `normalized.wav` and a desired window duration `WINDOW_SEC`:

- **Pad** if too short:

  ```bash
  ffmpeg -hide_banner -y -i normalized.wav -af "apad=pad_dur=WINDOW_SEC,atrim=duration=WINDOW_SEC" seg_fit.wav
  ```

- **Trim** if too long:

  ```bash
  ffmpeg -hide_banner -y -i normalized.wav -af "atrim=duration=WINDOW_SEC" seg_fit.wav
  ```

- **Rate adjust** (small changes): use `atempo` (0.5–2.0 per stage; chain if needed) then trim/pad to exactly `WINDOW_SEC`.

Re-run loudness normalization after significant tempo changes.

## 7. Output directories and reproducibility

In some environments the output root directory may be a mounted path you cannot delete. Prefer clearing contents instead of removing the directory:

```bash
OUT_DIR="<task-specified-output-dir>"
mkdir -p "$OUT_DIR"
rm -rf "$OUT_DIR"/*
```
