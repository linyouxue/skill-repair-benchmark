# Pick Extraction from SeisBench Picking Models

Read this when you must use `annotate()` output directly — for example, to
inspect the probability characteristic function, apply a custom threshold, or
work with a model whose `classify()` output is insufficient for your deliverable.
If `classify()` already gives you the discrete picks you need, use it and skip
this file.

## Mechanism: why annotate() indices need a blinding correction

SeisBench picking models (PhaseNet, EQTransformer, and similar) run in a
sliding-window fashion. The network's prediction at the extreme edge of each
window is unreliable, so the model trims (blinds) `N_blind` samples from each
edge of every prediction before stitching windows together. The annotation
`Trace` returned by `annotate()` therefore has fewer samples than the input
(e.g. 11500 vs 12000 for PhaseNet at default settings → `N_blind = 250` per
edge), but SeisBench reports the annotation trace's `starttime` equal to the
input stream's `starttime`. In other words: the first annotation sample
actually represents input sample `N_blind`, NOT input sample 0, yet
`ann[0].stats.starttime + i * ann[0].stats.delta` acts as if it represents
sample 0. The hand-rolled index is therefore wrong by `N_blind` samples
(2.5 s at 100 Hz) — far larger than typical evaluation tolerances (0.1 s).

## Preferred branch: use classify()

```python
import seisbench.models as sbm

model = sbm.PhaseNet.from_pretrained("original")
outputs = model.classify(stream)          # handles blinding + thresholding
picks = outputs.picks                      # list of Pick objects

rows = []
for pick in picks:
    rows.append({
        "trace_id": pick.trace_id,         # NET.STA.LOC.CHA
        "phase":    pick.phase,            # "P" or "S"
        "peak_time": pick.peak_time,       # UTCDateTime, correct on input axis
        "peak_value": pick.peak_value,     # probability at the peak
    })
```

`classify()` already (a) corrects for blinding, (b) drops low-probability
candidates below the model's default threshold, and (c) may return zero, one,
or many picks per trace — do not assume a fixed count per stream.

## Fallback branch: annotate() with explicit reconciliation

Only use this branch when you need the raw characteristic function (e.g. to
threshold yourself, or to plot probabilities). The branch has three steps:
compute, reconcile against `classify()` on one known trace, then apply.

```python
import numpy as np

annotations = model.annotate(stream)       # Stream of probability traces
p_tr = annotations.select(channel="*_P")[0]
prob = p_tr.data
threshold = 0.3                             # pick your own threshold

# Candidate peaks above threshold — not a forced single argmax
above = np.where(prob > threshold)[0]
if above.size == 0:
    hand_rolled_time = None
else:
    i_peak = above[np.argmax(prob[above])]
    # WARNING: this time is off by the blinding width — correct below.
    naive_time = p_tr.stats.starttime + i_peak * p_tr.stats.delta
```

### Verification step (required before bulk processing)

Run `classify()` on the same input and compare against your hand-rolled time
on at least one known trace. If they disagree, the hand-rolled path is wrong.

```python
ref = model.classify(stream).picks
ref_p = [p for p in ref if p.phase == "P"]
if ref_p and hand_rolled_time is not None:
    delta_s = abs(float(ref_p[0].peak_time - naive_time))
    delta_samples = round(delta_s * p_tr.stats.sampling_rate)
    tol_samples = 2                         # tolerate rounding only
    if delta_samples > tol_samples:
        # Corrective action: compute the blinding offset from the
        # length mismatch and re-map, then re-verify.
        input_tr = stream.select(id=p_tr.id.replace("_P", ""))[0] \
                   if False else stream[0]  # pick the matching raw trace
        n_blind = (input_tr.stats.npts - p_tr.stats.npts) // 2
        corrected_time = naive_time + n_blind * p_tr.stats.delta
        # Re-run the comparison; if it still fails, STOP and switch to
        # classify() entirely — do not ship hand-rolled picks in bulk.
        delta_s2 = abs(float(ref_p[0].peak_time - corrected_time))
        assert delta_s2 * p_tr.stats.sampling_rate <= tol_samples, (
            "annotate-based mapping still disagrees with classify() after "
            "blinding correction; fall back to classify() for the full run."
        )
```

The rule is: a round-number disagreement between a library-native method
(`classify()`) and a hand-rolled replacement (`argmax(annotate())` mapped by
hand) is almost always a hidden model parameter (here: `N_blind`). Never
scale up until the disagreement is explained or eliminated.

## When classify() is not enough

Rare situations where the fallback branch is the right call:

- You need the full probability time series (e.g. to export a heatmap).
- You want a custom, task-specific threshold different from the model
  default.
- You are debugging a model and want to see raw argmax positions.

In all three, still run the verification step above once per model/version
before trusting hand-rolled times in bulk.
