---
name: seisbench-model-api
description: Use SeisBench waveforms models via ObsPy Streams, preferring classify() outputs for time-aligned picks and using annotate() only with explicit alignment and sanity checks.
---

# SeisBench Model API

## Quick workflow (avoid systematic pick bugs)

1. Prefer `model.classify(stream, ...)` when you need discrete picks (times/labels); treat `annotate()` outputs as intermediate characteristic functions.
2. Before exporting indices, confirm what time base you are in (original trace vs annotation trace) by checking `stats.starttime`, `stats.delta`, and `stats.npts`.
3. Sanity-check outputs across many files: pick indices should not suspiciously cluster to a narrow band; if they do, suspect a mapping/alignment bug before tuning thresholds.

## Annotate vs classify

Use `annotate()` to obtain per-sample probabilities/characteristic functions; use `classify()` to obtain discrete objects (e.g., picks/detections) in the model’s intended reference frame.

```python
import seisbench.models as sbm

model = sbm.WaveformModel.from_pretrained("...")
model.eval()

ann = model.annotate(stream)
out = model.classify(stream, **thresholds)

print(type(ann), len(ann))
print(type(out), getattr(out, "picks", None))
```

Decision rule: If you ultimately need arrival times/indices for a CSV, start from `classify()` unless you have a tested, model-specific alignment procedure for `annotate()`.

Read references/seisbench-phasenet-picking.md when using PhaseNet (or similar pickers) and you plan to convert model outputs into sample indices.
Skip when you only need the raw probability traces for visualization.

## Converting pick times to sample indices (generic)

Convert timestamps to indices using the *same* trace’s `starttime` and `sampling_rate` that define the target index space.

```python
def time_to_index(peak_time, tr):
    sr = float(tr.stats.sampling_rate)
    dt = float(peak_time - tr.stats.starttime)
    return int(round(dt * sr))

# later: pick_idx = time_to_index(pick.peak_time, original_trace)
```

Decision rule: If `peak_time` is not in the same reference as `original_trace.stats.starttime`, do not convert; instead, first fix/validate the time base (see L3).

## Common pitfalls

- Treating `annotate()` output indices as 1:1 with the original waveform samples without verifying `starttime`/`npts` alignment.
- Using global `argmax` and emitting exactly one pick per phase per file regardless of confidence; this inflates false positives.
- Skipping dataset-level sanity checks (e.g., clustered indices) before writing final CSV outputs.
