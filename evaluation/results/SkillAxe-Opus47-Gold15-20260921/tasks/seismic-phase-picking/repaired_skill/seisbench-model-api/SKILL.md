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

### Numerical scaling
- If the waveform data happen to be extremely small in scale (`<=1e-10`), there might be risk of numerical instability. It is acceptable to increase the value first (by multiplying a large number like `1e10`) before normalization or passing to the model.
- Although the seisbench model API will normalize the waveform for you, it is still highly suggested to apply normalization yourself. Since seisbench's normalization scheme uses an epsilon `(waveform - mean(waveform)) / (std(waveform) + epsilon)`, for extremely small values (such as `<=1e-10`), their normalization can destroy the signals in the waveform.

### Building the input Stream correctly (critical for picker accuracy)
SeisBench routes traces to model channels using the `channel` code in `Trace.stats` (last character: `Z` = vertical, `N`/`1` and `E`/`2` = horizontals). Getting this wrong is one of the most common causes of degraded S-wave recall, because S detection relies heavily on horizontal components.

When loading custom arrays (e.g. from npz) into a Stream, always:
1. Set `stats.starttime`, `stats.delta` (or `sampling_rate`), `stats.network`, `stats.station`, `stats.location`, and above all `stats.channel` with the correct SEED-style code.
2. **Check for zero-padded / missing components.** Some datasets store single- or two-component records inside a fixed-shape `(N, 3)` array with the unused columns filled with zeros. The `channels` metadata (e.g. `"EHZ"` alone) tells you how many real components there are. Feeding all-zero traces into the model can trigger spurious activations after normalization; do **not** blindly create three Traces from a `(N,3)` array. Instead, keep only the columns that have non-zero data and pair them with the corresponding channel codes in order.
3. If a record has only a vertical component, PhaseNet/EQTransformer can still produce P picks but S recall will be lower; that is expected — do not fabricate horizontal channels by copying Z.

### Preprocessing recommended before `classify` / `annotate`
Even though the models will normalize internally, applying standard seismological preprocessing on the ObsPy Stream measurably improves picking F1, especially for S waves and out-of-distribution data:
- `stream.detrend("demean")` and `stream.detrend("linear")`
- `stream.taper(max_percentage=0.001, type="cosine")`
- `stream.filter("bandpass", freqmin=1.0, freqmax=45.0)` (typical for local earthquakes at 100 Hz)
- Resample to `model.sampling_rate` if it differs from the data sampling rate.

### Choosing thresholds and using multiple models
- `classify` accepts `P_threshold` and `S_threshold`. Lower thresholds (e.g. 0.1–0.2) increase recall at the cost of more false picks; higher thresholds (0.3–0.5) increase precision. When the evaluation is F1 on a small dataset, start around 0.2 and adjust; do not leave defaults untried.
- The seisbench model API can process a stream of arbitrary length. It is not necessary to segment the data yourself, and a stream may contain more than one P/S pair or none at all — treat it as continuous data.
- Pretrained weights are trained on specific networks/regions. If picks are systematically slightly off (out-of-distribution error 0.1–0.5 s per the picker-selection skill), try multiple pretrained weights (e.g. `PhaseNet` `scedc`, `stead`, `instance`, `original`) and/or a different architecture (`EQTransformer`), then either pick the best per-trace or ensemble the pick times (e.g. keep picks that agree within tolerance). This is often the difference between missing the ±0.1 s tolerance and hitting it.

### Reading picks back into indices
`classify` returns picks with `peak_time` as `UTCDateTime`. Convert to sample index as `int(round((peak_time - stream[0].stats.starttime) / dt))` and clip to `[0, N)` before writing.
