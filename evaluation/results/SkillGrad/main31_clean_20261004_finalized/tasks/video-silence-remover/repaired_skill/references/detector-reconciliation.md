# Detector reconciliation (energy vs silencedetect)

Use this when you have two (or more) candidate segment lists for the same phenomenon (opening cut or pauses), especially when one list is coarse (integer-second) or when a boundary is implausible.

## Goal

Produce one final removal list that is (a) internally consistent, (b) conservative about not clipping speech, and (c) supported by quick boundary spot-checks.

## Procedure (with runtime branches)

```python
from __future__ import annotations

# Inputs at runtime:
# energy_segments, ffmpeg_segments: list[dict] like {"start": ..., "end": ...}
# kind: "opening" or "pause"


def norm(segs):
    out = []
    for s in segs:
        a, b = float(s["start"]), float(s["end"])
        if b > a:
            out.append((a, b))
    return sorted(out)


def merge_overlaps(segs, gap=0.0):
    merged = []
    for a, b in segs:
        if not merged or a > merged[-1][1] + gap:
            merged.append([a, b])
        else:
            merged[-1][1] = max(merged[-1][1], b)
    return [(a, b) for a, b in merged]


def pad(segs, pre=0.15, post=0.15, lo=0.0):
    return [(max(lo, a - pre), b + post) for a, b in segs]


E = merge_overlaps(norm(energy_segments), gap=0.1)
F = merge_overlaps(norm(ffmpeg_segments), gap=0.1)

# Pick a primary source + verification strategy
# Branch A: opening cut — prefer ffmpeg-derived boundary if it finds early non-silence
if kind == "opening":
    # candidate boundary: earliest non-zero-length initial segment starting at 0
    e0 = next((s for s in E if abs(s[0] - 0.0) < 1e-6), None)
    f0 = next((s for s in F if abs(s[0] - 0.0) < 1e-6), None)

    # If energy suggests a very long opening but ffmpeg doesn't, treat energy as suspicious.
    if e0 and (e0[1] > 60) and (not f0 or f0[1] < e0[1] - 5):
        proposed = f0 if f0 else (0.0, 60.0)
        action = "PROBE_BOUNDARY"  # verify; do not accept the long energy-based cut
    else:
        proposed = f0 or e0
        action = "PROBE_BOUNDARY" if proposed else "NO_OPENING_CUT"

# Branch B: pauses — take intersection-ish behavior conservatively
else:
    # Keep segments supported by either detector, but snap boundaries toward the more conservative (shorter) cut.
    proposed = merge_overlaps(E + F, gap=0.3)
    proposed = pad(proposed, pre=0.2, post=0.2, lo=0.0)
    action = "PROBE_SAMPLE" if proposed else "NO_PAUSES"

print({"action": action, "n_energy": len(E), "n_ffmpeg": len(F), "n_proposed": 0 if not proposed else (1 if kind=="opening" else len(proposed))})
```

## Verification

- **Opening:** probe audio at ~5s before the proposed boundary and ~1s after it; confirm the inside snippet is non-content and the after snippet contains sustained content.
- **Pauses:** probe 3–5 randomly selected pause boundaries (start/end) and confirm you are not clipping words.

## Corrective action on failure

- If probes show speech inside a proposed removal segment: shorten the segment to the last verified non-speech time, add padding (reduce pre/post), and re-probe.
- If energy and ffmpeg disagree widely across many boundaries: re-run the detector you trust more with adjusted parameters (e.g., silencedetect threshold) and repeat reconciliation.
- If the final list still looks coarse (integer seconds) near speech: refine boundaries by probing in smaller steps (e.g., +/-0.5s) until stable.
