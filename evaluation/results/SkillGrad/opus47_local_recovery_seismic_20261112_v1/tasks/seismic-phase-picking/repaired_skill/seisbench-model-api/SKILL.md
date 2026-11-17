---
name: seisbench-model-api
description: Core model API of SeisBench — a Python framework for applying pretrained ML models (phase picking, earthquake detection, denoising, depth estimation) to seismic waveforms via obspy streams.
---

# SeisBench Model API

## Installing SeisBench
The recommended way is installation through pip. Simply run:
```
pip install seisbench
```

## Overview

SeisBench offers the abstract class `WaveformModel` that every SeisBench model should subclass. This class offers two core functions, `annotate` and `classify`. Both of the functions are automatically generated based on configurations and submethods implemented in the specific model.

The `SeisBenchModel` bridges the gap between the pytorch interface of the models and the obspy interface common in seismology. It automatically assembles obspy streams into pytorch tensors and reassembles the results into streams. It also takes care of batch processing. Computations can be run on GPU by simply moving the model to GPU.

The `annotate` function takes an obspy stream object as input and returns annotations as stream again. For example, for picking models the output would be the characteristic functions, i.e., the pick probabilities over time.

```python
stream = obspy.read("my_waveforms.mseed")
annotations = model.annotate(stream)  # Returns obspy stream object with annotations
```

The `classify` function also takes an obspy stream as input, but in contrast to the `annotate` function returns discrete results. The structure of these results might be model dependent. For example, a pure picking model will return a list of picks, while a picking and detection model might return a list of picks and a list of detections.

```python
stream = obspy.read("my_waveforms.mseed")
outputs = model.classify(stream)  # Returns a list of picks
print(outputs)
```

Both `annotate` and `classify` can be supplied with waveforms from multiple stations at once and will automatically handle the correct grouping of the traces. For details on how to build your own model with SeisBench, check the documentation of `WaveformModel`. For details on how to apply models, check out the Examples.

## Preparing Waveforms and Weights Before `classify()`

SeisBench's `annotate()`/`classify()` apply an internal `(x - mean) / (std + epsilon)` normalization. If typical peak amplitude is comparable to or smaller than that epsilon, the signal is wiped out before it reaches the network — a silent failure whose output looks numerically plausible but is driven by `epsilon`, not the data. Two upstream decisions govern whether `classify()` produces meaningful picks: (1) preprocessing (amplitude scale, detrend/taper, bandpass), and (2) pretrained-weight choice (the `"original"` weights of any picker are a weak default when the station network, channel code, sampling rate, or region differs from the model's training set).

Minimum preparation before a bulk run:

```python
# 1. Inspect amplitude on a representative sample (e.g. first 5-10 files)
peak = max(abs(tr.data).max() for tr in sample_stream)
# 2. Rescale unconditionally if peak is small relative to typical epsilon.
#    For raw velocity (m/s) traces, peaks often sit well above 1e-10 and
#    still need rescaling — do NOT gate on a tight `peak < 1e-10` check.
if peak < 1e-3:
    for tr in stream:
        tr.data = tr.data * 1e9
# 3. Standard preprocessing
stream.detrend("demean").taper(0.05).filter("bandpass", freqmin=1, freqmax=20)
# 4. Try more than one weight set on a small subset before scaling up
for weights in ["stead", "instance", "scedc", "original"]:
    m = sbm.PhaseNet.from_pretrained(weights)
    picks = m.classify(sample_stream).picks
    print(weights, len(picks), np.mean([p.peak_value for p in picks] or [0]))
```

Decision rule: pick the weight set that produces a non-degenerate pick-time distribution (see "Sanity-checking Output Distribution" below) on the sample, then use it for the bulk run. If no weight set produces non-degenerate output, the preprocessing — not the weights — is the likely culprit.

Read references/preprocessing-and-weight-selection.md when (a) typical peak amplitude is small, raw instrument units are involved (`m/s`, `m/s^2`, counts with unknown gain), or the dataset's network/channel/region is out-of-distribution for the picker; or (b) you need the full amplitude-inspection + multi-weight comparison procedure. Skip when the dataset is known-in-distribution for the chosen weights AND amplitudes are already in a normalized range (e.g. order 1).

## Extracting Discrete Picks (P/S times)

When the deliverable is a list of discrete P/S pick times, call `classify()` and read each pick's `peak_time`, `peak_value`, and `phase` directly. `classify()` already (a) corrects for the model's internal edge blinding/trim, and (b) filters out low-probability candidates so streams without a real event do not force a false pick.

```python
outputs = model.classify(stream, P_threshold=0.2, S_threshold=0.2)
for pick in outputs.picks:
    t = pick.peak_time                    # UTCDateTime on the raw input axis
    prob = pick.peak_value                # model confidence
    phase = pick.phase                    # "P" or "S"
```

`P_threshold` / `S_threshold` are tunable: lower them (e.g. 0.1-0.2) when the task is recall-limited (few picks produced on data that should contain events, F1 bottlenecked by missed picks); raise them when precision-limited (many false picks). Defaults are usually ~0.3-0.5; always pass them explicitly for reproducibility.

Do NOT compute pick times as `ann[0].stats.starttime + argmax_i * ann[0].stats.delta` on an `annotate()` output. Picking models (PhaseNet-class) trim N samples from each edge of every prediction window, so the annotation trace is shorter than the input, but its reported `starttime` is unshifted — hand-rolled indices are off by the blinding width (often hundreds of samples, i.e. seconds at typical sampling rates). Do not assume one P and one S per stream either: a stream may contain zero, one, or many picks of each phase.

Read references/pick-extraction.md when you must work with `annotate()` output directly (e.g. to inspect probabilities, apply a custom threshold, or because `classify()` output is insufficient). Skip when `classify()` already returns everything you need.

## Loading Pretrained Models

For annotating waveforms in a meaningful way, trained model weights are required. SeisBench offers a range of pretrained model weights through a common interface. Model weights are downloaded on the first use and cached locally afterwards. For some model weights, multiple versions are available. For details on accessing these, check the documentation at `from_pretrained`.

```python
import seisbench.models as sbm

sbm.PhaseNet.list_pretrained()                  # Get available weight sets
model = sbm.PhaseNet.from_pretrained("original")
```

The first weight set you try is almost never the best one for an unfamiliar dataset. The seismic-picker-selection guide notes that out-of-distribution pick errors of 0.1-0.5 s are routine — already above typical evaluation tolerances. Sample multiple weight sets on a small subset before committing to a bulk run; see "Preparing Waveforms and Weights" above.

## Speeding Up Model Application

When applying models to large datasets, run time is often a major concern. Here are a few tips to make your model run faster:

- **Run on GPU.** Execution on GPU is usually faster, even though exact speed-ups vary between models. However, we note that running on GPU is not necessarily the most economic option. For example, in cloud applications it might be cheaper (and equally fast) to pay for a handful of CPU machines to annotate a large dataset than for a GPU machine.

- **Use a large `batch_size`.** This parameter can be passed as an optional argument to all models. Especially on GPUs, larger batch sizes lead to faster annotations. As long as the batch fits into (GPU) memory, it might be worth increasing the batch size.

- **Compile your model (torch 2.0+).** If you are using torch in version 2.0 or newer, compile your model. It's as simple as running `model = torch.compile(model)`. The compilation will take some time but if you are annotating large amounts of waveforms, it should pay off quickly. Note that there are many options for compile that might influence the performance gains considerably.

- **Use asyncio interface.** Load data in parallel while executing the model using the asyncio interface, i.e., `annotate_asyncio` and `classify_asyncio`. This is usually substantially faster because data loading is IO-bound while the actual annotation is compute-bound.

- **Manual resampling.** While SeisBench can automatically resample the waveforms, it can be faster to do the resampling manually beforehand. SeisBench uses obspy routines for resampling, which (as of 2023) are not parallelised. Check the required sampling rate with `model.sampling_rate`. Alternative routines are available, e.g., in the Pyrocko library.

## Models Integrated into SeisBench

You don't have to build models from scratch if you don't want to. SeisBench integrates the following notable models from the literature for you to use. Again, as they inherit from the common SeisBench model interface, all these deep learning models are constructed through PyTorch. Where possible, the original trained weights are imported and made available. These can be accessed via the `from_pretrained` method.

| Integrated Model | Task |
|------------------|------|
| `BasicPhaseAE` | Phase Picking |
| `CRED` | Earthquake Detection |
| `DPP` | Phase Picking |
| `DepthPhaseNet` | Depth estimation from depth phases |
| `DepthPhaseTEAM` | Depth estimation from depth phases |
| `DeepDenoiser` | Denoising |
| `SeisDAE` | Denoising |
| `EQTransformer` | Earthquake Detection/Phase Picking |
| `GPD` | Phase Picking |
| `LFEDetect` | Phase Picking (Low-frequency earthquakes) |
| `OBSTransformer` | Earthquake Detection/Phase Picking |
| `PhaseNet` | Phase Picking |
| `PhaseNetLight` | Phase Picking |
| `PickBlue` | Earthquake Detection/Phase Picking |
| `Skynet` | Phase Picking |
| `VariableLengthPhaseNet` | Phase Picking |

Currently integrated models are capable of earthquake detection and phase picking, waveform denoising, depth estimation, and low-frequency earthquake phase picking. Furthermore, with SeisBench you can build ML models to perform general seismic tasks such as magnitude and source parameter estimation, hypocentre determination etc.

## Sanity-checking Output Distribution

Before shipping bulk pick output, inspect the distribution of pick positions within each input window. ML pipelines fail silently in characteristic shapes: picks clustered at a trivial location (window center, window start, window end), identical peak_value across files, exactly one pick per file. Any of these is a degeneracy signal, not a success signal.

```python
# pick_sample = sample index of the pick within its window
import pandas as pd
df = pd.DataFrame(rows)
print(df.groupby("phase")["pick_sample"].describe())
# Red flags: std << window_length, mean sitting at window_length // 2,
# identical pick_value across all rows.
```

Decision rule: if picks cluster at a trivial window position OR peak_value is near-constant, do NOT ship. Treat it as an upstream input problem (normalization collapse, wrong sampling rate, wrong channel orientation) and return to "Preparing Waveforms and Weights" — try rescaling, a different weight set, or a different preprocessing filter before re-running. Also spot-check 2-3 picks against the raw waveform envelope: a pick should align with a visible amplitude increase.

## Best Practices
- Preprocess upstream of the model (amplitude rescale when needed, detrend, taper, bandpass). SeisBench's internal `(x-mean)/(std+epsilon)` normalization can destroy small-amplitude signals when peak `|x|` is comparable to `epsilon` — raw `m/s` channels are a common case even when peak amplitude is well above `1e-10`. See "Preparing Waveforms and Weights Before `classify()`" above.
- Prefer `classify()` over hand-rolled `annotate()` indexing (blinding trap) and do not assume exactly one P and one S per stream. See "Extracting Discrete Picks".
- Pass `P_threshold`/`S_threshold` explicitly and tune them to the task's precision/recall balance rather than relying on defaults.

## Common Pitfalls
- Trusting `ann[0].stats.starttime` on an `annotate()` output as if it were the input axis — the model's edge blinding is NOT reflected in that starttime, so `starttime + argmax * delta` is systematically off by the blinding width. Prefer `classify()`; see "Extracting Discrete Picks".
- Emitting a pick per stream unconditionally (forced one-P-one-S per file) — `argmax` on a noise-only annotation returns an arbitrary index. Let `classify()` filter by probability, or apply an explicit threshold before writing output.
- Treating a numerical threshold cited in the skill (e.g. `<=1e-10`) as a strict gate when it is a floor for *guaranteed* destruction, not a ceiling for when preprocessing helps. The general rule: compare typical peak amplitude against the model's normalization epsilon, and rescale whenever they are comparable.
- Shipping results from the first pretrained weight set tried on an out-of-distribution dataset. OOD pick errors of 0.1-0.5 s are routine and alone can zero out a tight-tolerance score.
- Interpreting output clustered at a trivial location (window center / start / end) as a consistent arrival. It is the classic signature of degenerate input (normalization collapse, wrong sampling rate, wrong channel orientation) — the model is returning its prior, not responding to signal. See "Sanity-checking Output Distribution".
- Proceeding to bulk processing after a debug run shows a library-native result (e.g. `classify()` `peak_time`) disagreeing with a hand-rolled result (e.g. `argmax(annotate())` mapped by hand), especially when the delta is a round number matching a known model parameter. Reconcile first; the library-native path is authoritative unless you can explain the delta mechanistically.
