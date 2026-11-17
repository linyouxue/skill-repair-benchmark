# Preprocessing and Pretrained-Weight Selection for SeisBench Pickers

Read this when applying a SeisBench picking model (PhaseNet, EQTransformer,
GPD, etc.) to a dataset whose amplitude scale, instrument units, or source
region may differ from the model's training distribution. Two upstream
decisions determine whether `classify()` produces useful picks: the state of
the waveforms when the model receives them, and which pretrained weight set
is loaded. Getting either wrong causes silent, high-volume failures where the
output looks numerically plausible but every pick is noise.

## Mechanism: why upstream preparation decides the run

SeisBench's model API applies an internal normalization
`x_norm = (x - mean(x)) / (std(x) + epsilon)` before the network. When
`std(x)` is small relative to `epsilon`, the denominator is `~epsilon`,
so `x_norm` is dominated by `epsilon` — the network sees near-constant
input and returns its prior (typically a mild bump near the window centre,
yielding picks clustered at a trivial sample index). Raw velocity (`m/s`)
and acceleration (`m/s^2`) channels frequently fall into this regime even
when peak amplitudes are nowhere near `1e-10` — peaks in the `1e-7..1e-4`
range are already small compared to typical epsilon values.

Separately, pretrained picker weights are trained on a specific population
of stations/instruments/regions. The seismic-picker-selection guide quotes
out-of-distribution pick errors of `0.1-0.5 s` — already at or above the
`0.1 s` tolerance typical of F1 scoring. For short-period local-network
data (channel codes like `DP?`, `EH?`, `SH?`), PhaseNet's `"original"`
weights (trained on NCEDC broadband) are a weak default; `stead`,
`instance`, `scedc`, and `geofon` should be sampled.

## Step 1: inspect amplitude distribution across the dataset

```python
import numpy as np, glob, obspy

files = sorted(glob.glob("data/*.mseed"))[:10]   # representative sample
peaks = []
for f in files:
    st = obspy.read(f)
    for tr in st:
        peaks.append(float(np.abs(tr.data).max()))
peaks = np.array(peaks)
print("median peak |x|:", np.median(peaks), "range:", peaks.min(), peaks.max())
```

Branch:

- **Peak < ~1e-3 (any magnitude close to or below SeisBench's epsilon):**
  rescale unconditionally (step 2). Do NOT use a narrow `peak < 1e-8` or
  `peak < 1e-10` guard — that threshold excludes most raw `m/s` data that
  still needs rescaling.
- **Peak in ~1e-3 to ~1e+3 range:** rescale is probably unnecessary; proceed
  to step 3.
- **Peak > ~1e+3 (e.g. counts):** consider dividing to bring into order-1
  range; extremely large magnitudes can also cause numerical issues in
  downstream filters.

## Step 2: rescale unconditionally when needed

```python
SCALE = 1e9                                   # or 1e10 — magnitude matters,
                                              # exact value does not
for tr in stream:
    tr.data = tr.data.astype(np.float64) * SCALE
```

A multiplicative rescale cannot change pick times (it commutes with every
linear preprocessing step and with the model's own normalization *once the
denominator stops being epsilon-dominated*). The purpose is to move the
signal out of the `std <~ epsilon` regime, nothing more. Apply to every
trace; do not condition per-trace on local amplitude because quiet traces
are exactly the ones you need to rescue.

## Step 3: standard preprocessing

```python
stream.detrend("demean")
stream.detrend("linear")
stream.taper(max_percentage=0.05, type="cosine")
stream.filter("bandpass", freqmin=1.0, freqmax=20.0,
              corners=4, zerophase=True)
```

Frequency band depends on the data: 1-20 Hz for local-earthquake short-period
channels (hundreds of Hz events), 0.5-10 Hz for regional broadband, higher
cuts for ocean-bottom instruments. If unsure, inspect a spectrogram of one
event trace first.

## Step 4: multi-weight trial on a small subset

```python
import seisbench.models as sbm

candidate_weights = ["original", "stead", "instance", "scedc", "geofon"]
sample = stream.copy()                        # already preprocessed
summary = []
for w in candidate_weights:
    try:
        m = sbm.PhaseNet.from_pretrained(w)
    except Exception as e:
        print(f"skip {w}: {e}"); continue
    picks = m.classify(sample, P_threshold=0.2, S_threshold=0.2).picks
    n_p = sum(1 for p in picks if p.phase == "P")
    n_s = sum(1 for p in picks if p.phase == "S")
    mean_prob = (np.mean([p.peak_value for p in picks])
                 if picks else 0.0)
    summary.append((w, n_p, n_s, mean_prob))
    print(w, n_p, n_s, round(mean_prob, 3))
```

Decision rule: prefer the weight set that (a) returns non-degenerate pick
counts on the sample (not zero, not exactly one-per-trace) AND (b) whose
pick times are distributed across the window rather than clustered at the
centre (see verification step). Flag `"original"` PhaseNet weights as a
weak default for short-period local-network data — pick a trained-on-local
alternative (`stead`, `instance`, `scedc`) when available.

## Step 5: verification — non-degenerate output distribution

Required before scaling to the full dataset.

```python
import pandas as pd

# Re-run the best candidate on the sample and gather sample indices
best = sbm.PhaseNet.from_pretrained(summary_sorted_best_name)
rows = []
for tr in sample:
    picks = best.classify(obspy.Stream([tr]),
                          P_threshold=0.2, S_threshold=0.2).picks
    for p in picks:
        i = int(round((p.peak_time - tr.stats.starttime)
                      * tr.stats.sampling_rate))
        rows.append({"trace": tr.id, "phase": p.phase,
                     "pick_sample": i, "npts": tr.stats.npts,
                     "peak_value": p.peak_value})

df = pd.DataFrame(rows)
print(df.groupby("phase")["pick_sample"].describe())

# Branch: inspect for degeneracy
centre = int(sample[0].stats.npts // 2)
tol = 50                                        # samples
degenerate = (
    df.empty
    or (df["pick_sample"].sub(centre).abs() < tol).mean() > 0.8
    or df["peak_value"].std() < 1e-4
)
if degenerate:
    # Corrective action: do NOT proceed to bulk run. Return to step 1:
    #   - re-check amplitude after rescale (did std actually grow?)
    #   - try a stronger bandpass or a different corner frequency
    #   - try the next weight set in the candidate list
    #   - if all candidate weights degenerate, suspect wrong channel
    #     orientation (Z/N/E vs 1/2/3) or wrong sampling rate
    raise RuntimeError("degenerate pick distribution — fix upstream "
                       "before bulk run")
else:
    print("OK — distribution looks non-degenerate; proceed to bulk run")
```

The verification step is mandatory because every failure mode above is
silent otherwise: the CSV fills with rows, counts look reasonable, and
only the position distribution reveals that the model never saw signal.

## When to skip this chapter

- The waveform data are already normalized to order-1 by an upstream
  pipeline AND the chosen weight set is known to match the dataset
  (e.g. a known benchmark). In that case `classify()` output can be
  trusted without the multi-weight trial — but still run the Step 5
  distribution check once.
