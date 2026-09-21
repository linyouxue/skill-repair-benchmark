---
name: seisbench-model-api
description: An overview of the core model API of SeisBench, a Python framework for training and applying machine learning algorithms to seismic data. It is useful for annotating waveforms using pretrained SOTA ML models, for tasks like phase picking, earthquake detection, waveform denoising and depth estimation. For any waveform, you can manipulate it into an obspy stream object and it will work seamlessly with seisbench models.
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

## Loading Pretrained Models

For annotating waveforms in a meaningful way, trained model weights are required. SeisBench offers a range of pretrained model weights through a common interface. Model weights are downloaded on the first use and cached locally afterwards. For some model weights, multiple versions are available. For details on accessing these, check the documentation at `from_pretrained`.

```python
import seisbench.models as sbm

sbm.PhaseNet.list_pretrained()                  # Get available models
model = sbm.PhaseNet.from_pretrained("original")  # Load the original model weights released by PhaseNet authors
```

Pretrained models can not only be used for annotating data, but also offer a great starting point for transfer learning.

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

## Best Practices
- If the waveform data happen to be extremely small in scale (`<=1e-10`), there might be risk of numerical instability. It is acceptable to increase the value first (by multiplying a large number like `1e10`) before normalization or passing to the model.

- Although the seisbench model API will normalize the waveform for you, it is still highly suggested to apply normalization yourself. Since seisbench's normalization scheme uses an epsilon `(waveform - mean(waveform)) / (std(waveform) + epsilon)`, for extremely small values (such as `<=1e-10`), their normalization can destroy the signals in the waveform.

- The seisbench model API can process a stream of waveform data of arbitrary length. Hence, it is not necessary to segment the data yourself. In addition, you should not assume a stream of waveform can only contain one P-wave and one S-wave. It is the best to treat the stream like what it is: a stream of continuous data.



## End-to-End Workflow for Custom NPZ Phase Picking

For each input NPZ, validate the required fields before invoking SeisBench and preserve the original sample coordinate system:

```python
import numpy as np


def load_npz(path):
    with np.load(path, allow_pickle=False) as z:
        missing = {"data", "dt", "channels"} - set(z.files)
        if missing:
            raise ValueError(f"{path}: missing {sorted(missing)}")
        x = np.asarray(z["data"])
        dt = float(np.asarray(z["dt"]).reshape(()))
        raw = np.asarray(z["channels"]).reshape(()).item()
        channels = [s.strip() for s in str(raw).split(",") if s.strip()]
    if x.ndim != 2 or len(channels) != 3 or not np.isfinite(dt) or dt <= 0:
        raise ValueError(f"{path}: expected finite 2-D three-component data and dt>0")
    if x.shape[1] == len(channels):
        x = x.astype(np.float32, copy=False)       # samples x components
    elif x.shape[0] == len(channels):
        x = x.T.astype(np.float32, copy=False)
    else:
        raise ValueError(f"{path}: data shape {x.shape} disagrees with channels")
    if not np.isfinite(x).all():
        raise ValueError(f"{path}: waveform contains NaN or infinity")
    return x, dt, channels
```

Do not silently guess an orientation, duplicate component, or invalid metadata; skip the file with a diagnostic or use the documented fallback. Keep `n_samples`, `dt`, and every preprocessing/window offset so a model time can later be converted back to the untrimmed source index.



## Build and Verify the SeisBench Input Stream

Construct aligned ObsPy traces using the file-specific sampling rate. Channel labels must drive the component mapping; never assume that the columns are Z,N,E. A common three-component mapping is a code ending in `Z` for vertical and codes ending in `N`/`1` and `E`/`2` for horizontals, but reject ambiguous or duplicate mappings rather than inventing one.

```python
from obspy import Stream, Trace, UTCDateTime


def make_stream(x, dt, channels):
    start = UTCDateTime(0)  # relative origin when the file has no acquisition time
    return Stream([
        Trace(data=x[:, j].copy(), header={
            "channel": ch,
            "starttime": start,
            "sampling_rate": 1.0 / dt,
        }) for j, ch in enumerate(channels)
    ])


def component_map(channels):
    groups = {}
    for j, ch in enumerate(channels):
        c = ch.upper().split(".")[-1]
        suffix = c[-1:] if c else ""
        groups.setdefault(suffix, []).append(j)
    z = [j for j, ch in enumerate(channels) if ch.upper().split(".")[-1].endswith("Z")]
    h1 = [j for j, ch in enumerate(channels) if ch.upper().split(".")[-1].endswith(("N", "1"))]
    h2 = [j for j, ch in enumerate(channels) if ch.upper().split(".")[-1].endswith(("E", "2"))]
    if len(z) != 1 or len(h1) != 1 or len(h2) != 1 or len({z[0], h1[0], h2[0]}) != 3:
        raise ValueError(f"unsupported or ambiguous component layout: {channels}")
    return {"Z": z[0], "H1": h1[0], "H2": h2[0]}
```

Before inference, inspect the installed model rather than assuming one release's API: use `getattr(model, "sampling_rate", None)` and any documented channel/component metadata. If the model has a required sampling rate, resample a copy only when necessary and map the resulting pick time back using elapsed seconds and the original `dt`. Confirm that the selected pretrained model accepts three components and that its expected order is satisfied; otherwise choose a compatible model or use the fallback. `UTCDateTime(0)` is only a relative bookkeeping origin, not a fabricated acquisition timestamp.



## CPU-Conscious, Version-Aware Inference and Pick Extraction

Model downloads are optional: try a locally cached or explicitly selected pretrained model, catch download/load errors, and do not make network access a prerequisite. Run on CPU by default (`model.to("cpu")` when supported), use `batch_size=1` or a small batch, and avoid assuming CUDA. For long records, infer overlapping windows and retain each window's source start sample. SeisBench can batch arbitrary streams, but explicit windows make memory use and coordinate conversion clear.

```python
import inspect
import numpy as np


def call_api(model, stream):
    # Signatures and return structures vary by SeisBench version.
    try:
        return model.classify(stream)
    except (AttributeError, TypeError, NotImplementedError):
        return model.annotate(stream)


def output_arrays(out):
    """Return (time arrays, P arrays, S arrays) for common annotation forms."""
    if out is None:
        return None
    if hasattr(out, "traces"):  # ObsPy Stream annotations
        vals = {}
        for tr in out:
            name = tr.stats.channel.upper()
            vals[name] = np.asarray(tr.data, dtype=float)
        p = next((v for k, v in vals.items() if "P" in k), None)
        s = next((v for k, v in vals.items() if "S" in k), None)
        return p, s
    if isinstance(out, dict):
        p = out.get("P", out.get("p", out.get("P_probability")))
        s = out.get("S", out.get("s", out.get("S_probability")))
        return (None if p is None else np.asarray(p, float),
                None if s is None else np.asarray(s, float))
    return None
```

When `classify` returns discrete picks, inspect each pick's phase and time fields rather than treating the object as an annotation curve. When `annotate` returns curves, locate P/S channels by their labels, reject empty, nonfinite, or all-zero outputs, and use `scipy.signal.find_peaks` (or a documented equivalent) with a phase-specific height/prominence and minimum-distance threshold. A probability peak's time may be represented by `trace.stats.starttime + i / sampling_rate`; convert it to the source index with `round((pick_time - source_starttime) / original_dt)`. For a window beginning at source sample `w0`, use `w0 + round(local_time / original_dt)`, not merely the local peak index. Clip neither silently nor out of bounds: reject indices outside `[0, n_samples)` and retain confidence for diagnostics. Merge overlapping-window duplicates by phase and time, keeping the highest-confidence candidate.



## Failure Handling and Classical Fallback

Treat model failure as an expected operational case: catch pretrained-weight download errors, incompatible channel layouts, unsupported sampling rates, runtime/OOM errors, malformed or empty `annotate`/`classify` results, and absent P/S outputs. Do not fabricate picks from a failed model. A CPU-only environment is normal; reduce window length/batch size before abandoning inference.

If no usable model output is available, run a deterministic NumPy/ObsPy fallback on the validated original-rate array. Detrend or normalize copies without changing the sample grid; use vertical energy/onset or STA/LTA for P and delayed horizontal energy/envelope or STA/LTA for S. Estimate noise from an early or robust low-amplitude region, require finite positive SNR/prominence, and allow no pick when evidence is insufficient. This fallback is a candidate generator, not a guarantee of a phase, and must return source indices directly. Do not force P-before-S or invent a missing phase.

Finally write `/root/results.csv` with exactly `file_name,phase,pick_idx`. Validate each row before writing: phase is exactly `P` or `S`, `pick_idx` is an integer in `[0, n_samples)`, and the filename is the actual input filename. Deduplicate identical phase/index rows, permit multiple or zero picks per file, and log skipped files and fallback use separately from the CSV.
