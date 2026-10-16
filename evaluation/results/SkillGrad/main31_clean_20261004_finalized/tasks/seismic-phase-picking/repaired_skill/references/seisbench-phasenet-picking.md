# SeisBench PhaseNet picking: aligned picks, thresholds, and index sanity checks

Use this chapter when you need to export PhaseNet (or similar SeisBench picker) outputs as sample indices and the evaluation is sensitive to systematic timing errors.

## Goal

- Produce P/S picks that are time-aligned to the *original* waveform traces.
- Avoid two recurrent failure modes:
  1) mis-mapping `annotate()` indices back to the original trace because of model windowing/blinding/cropping;
  2) forcing exactly one pick per phase via a global argmax, which inflates false positives.

## Procedure (prefer classify)

### Branch A — You can use `classify()` (recommended)

- Use `model.classify(stream, P_threshold=..., S_threshold=...)`.
- Convert each returned pick’s `peak_time` to an index in the target trace.
- Allow zero, one, or multiple picks per phase depending on what `classify()` returns.

```python
import numpy as np
import seisbench.models as sbm

model = sbm.PhaseNet.from_pretrained("...")
model.eval()

out = model.classify(stream, P_threshold=0.3, S_threshold=0.3)

# Map trace id -> trace for index conversion
tr_by_id = {tr.id: tr for tr in stream}
rows = []
for pick in getattr(out, "picks", []):
    tr = tr_by_id.get(pick.trace_id)
    if tr is None:
        continue
    sr = float(tr.stats.sampling_rate)
    idx = int(round(float(pick.peak_time - tr.stats.starttime) * sr))
    rows.append((pick.trace_id, pick.phase, idx, float(pick.peak_value)))

# Example post-filter: keep only plausible indices in-bounds
rows = [r for r in rows if r[2] >= 0 and r[2] < tr_by_id[r[0]].stats.npts]
```

### Branch B — You must use `annotate()` (only with explicit alignment work)

You must treat `annotate()` as producing a *different time series* than the input. Do not assume it has identical `npts` or `starttime`.

Steps:
1. Inspect per-trace alignment metadata (`starttime`, `delta`, `npts`) for both input and annotation.
2. Detect peaks with a threshold (not global argmax).
3. Convert annotation peak *times* (not indices) to original indices.
4. If you observe systematic clustering of indices, stop and switch to Branch A.

```python
import numpy as np

ann = model.annotate(stream)

# Simple local-max finder (generic, avoids global argmax)
def local_maxima(x):
    x = np.asarray(x)
    return np.where((x[1:-1] > x[:-2]) & (x[1:-1] >= x[2:]))[0] + 1

# Example: process each annotation trace independently
for ann_tr in ann:
    # Find its paired original trace by id
    orig_tr = next((t for t in stream if t.id == ann_tr.id), None)
    if orig_tr is None:
        continue

    # Alignment check: if these differ, you are in a remapped time base
    if (ann_tr.stats.starttime != orig_tr.stats.starttime) or (ann_tr.stats.npts != orig_tr.stats.npts):
        # You may still proceed, but only via time conversion.
        pass

    sr = float(orig_tr.stats.sampling_rate)
    peaks = local_maxima(ann_tr.data)

    threshold = 0.3
    peaks = [i for i in peaks if ann_tr.data[i] >= threshold]

    # Convert each annotation peak index -> annotation peak time -> original index
    for i in peaks:
        peak_time = ann_tr.stats.starttime + i * ann_tr.stats.delta
        idx = int(round(float(peak_time - orig_tr.stats.starttime) * sr))
        # use idx if 0 <= idx < orig_tr.stats.npts
```

## Verification and corrective action

### Verify 1 — Per-trace alignment metadata

Check a few traces:
- `ann_tr.stats.starttime` should not be blindly assumed equal to `orig_tr.stats.starttime`.
- `ann_tr.stats.npts` may be shorter due to edge blinding/cropping.

If you see differences and you are relying on direct index reuse (e.g., `idx = argmax(ann_tr)`), **stop** and switch to Branch A, or redo Branch B using time conversion plus the sanity checks below.

### Verify 2 — Dataset-level index distribution sanity check

Compute a coarse histogram of exported indices across many files.

```python
import numpy as np

pick_indices = np.asarray([idx for (_id, _ph, idx, _pv) in rows], dtype=int)

# Coarse check: are they all near the same place?
q05, q50, q95 = np.quantile(pick_indices, [0.05, 0.5, 0.95])
print("index quantiles:", q05, q50, q95)

# A very narrow spread relative to typical trace length is suspicious.
spread = int(q95 - q05)
print("spread:", spread)
```

If indices cluster into a narrow band across many traces (small `spread`):
1. assume an alignment/mapping bug first (not “the model is confident there”);
2. switch to Branch A (`classify()`), or re-check `annotate()` alignment and peak-finding (threshold + local maxima);
3. re-export and re-run this check before writing the final CSV.

### Verify 3 — In-bounds and ordering checks

- Ensure each exported index is within `[0, npts)`.
- If you enforce “S after P”, enforce it *after* time/index conversion and only when both picks exist.

If you get many out-of-bounds indices or frequent S<P violations:
- treat it as a mapping error or mis-paired traces (wrong `trace_id`), not a threshold tuning issue.
