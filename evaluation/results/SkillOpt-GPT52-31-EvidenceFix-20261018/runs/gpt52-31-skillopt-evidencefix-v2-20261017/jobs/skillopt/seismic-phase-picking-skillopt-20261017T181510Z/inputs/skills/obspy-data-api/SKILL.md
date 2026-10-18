---
name: obspy-data-api
description: An overview of the core data API of ObsPy, a Python framework for processing seismological data. It is useful for parsing common seismological file formats, or manipulating custom data into standard objects for downstream use cases such as ObsPy's signal processing routines or SeisBench's modeling API.
---

# ObsPy Data API

## Waveform Data

### Summary

Seismograms of various formats (e.g. SAC, MiniSEED, GSE2, SEISAN, Q, etc.) can be imported into a `Stream` object using the `read()` function.

Streams are list-like objects which contain multiple `Trace` objects, i.e. gap-less continuous time series and related header/meta information.

Each Trace object has the attribute `data` pointing to a NumPy `ndarray` of the actual time series and the attribute `stats` which contains all meta information in a dict-like `Stats` object. Both attributes `starttime` and `endtime` of the Stats object are `UTCDateTime` objects.

A multitude of helper methods are attached to `Stream` and `Trace` objects for handling and modifying the waveform data.



### ML / Phase-Picking Workflows

Modern seismic phase-picking models (e.g. SeisBench `PhaseNet`, `EQTransformer`, or custom PyTorch models) typically expect waveform data packaged as ObsPy `Trace`/`Stream` objects with consistent timing metadata and preprocessing.

Common preprocessing steps before inference:
- `detrend("demean")` or `detrend("linear")` to remove offsets/drift
- `taper()` to reduce edge artifacts
- `filter()` (often bandpass) to suppress noise
- `resample()` to the model's expected sample rate
- per-channel normalization or standardization
- verify equal sample counts and aligned start times across components

For 3-component data, preserve consistent component ordering. Many seismic ML pipelines assume `E`, `N`, `Z` ordering (or sometimes `Z`, `N`, `E` depending on the model). Always check the target model documentation and map channel names explicitly rather than relying on file order.

Incorrect `sampling_rate`, `delta`, `starttime`, or channel ordering can shift predicted pick indices and significantly degrade P/S arrival accuracy.

### Stream and Trace Class Structure

**Hierarchy:** `Stream` → `Trace` (multiple)

**Trace - DATA:**
- `data` → NumPy array
- `stats`:
  - `network`, `station`, `location`, `channel` — Determine physical location and instrument
  - `starttime`, `sampling_rate`, `delta`, `endtime`, `npts` — Interrelated

**Trace - METHODS:**
- `taper()` — Tapers the data.
- `filter()` — Filters the data.
- `resample()` — Resamples the data in the frequency domain.
- `integrate()` — Integrates the data with respect to time.
- `remove_response()` — Deconvolves the instrument response.


- `detrend()` — Removes mean or linear trend before ML inference.
- `normalize()` — Scales amplitudes for consistent model inputs.

Example preprocessing pipeline for phase picking:

```python
st.detrend("demean")
st.taper(max_percentage=0.05)
st.filter("bandpass", freqmin=1.0, freqmax=20.0)
st.resample(100)

# Optional per-trace normalization
for tr in st:
    peak = np.max(np.abs(tr.data))
    if peak > 0:
        tr.data = tr.data / peak
```

Many pretrained pickers are trained at fixed sample rates (commonly 100 Hz). Resample waveforms before inference so that pick indices map correctly to model expectations.

### Example

A `Stream` with an example seismogram can be created by calling `read()` without any arguments. Local files can be read by specifying the filename, files stored on http servers (e.g. at https://examples.obspy.org) can be read by specifying their URL.

```python
>>> from obspy import read
>>> st = read()
>>> print(st)
3 Trace(s) in Stream:
BW.RJOB..EHZ | 2009-08-24T00:20:03.000000Z - ... | 100.0 Hz, 3000 samples
BW.RJOB..EHN | 2009-08-24T00:20:03.000000Z - ... | 100.0 Hz, 3000 samples
BW.RJOB..EHE | 2009-08-24T00:20:03.000000Z - ... | 100.0 Hz, 3000 samples
>>> tr = st[0]
>>> print(tr)
BW.RJOB..EHZ | 2009-08-24T00:20:03.000000Z - ... | 100.0 Hz, 3000 samples
>>> tr.data
array([ 0.        ,  0.00694644,  0.07597424, ...,  1.93449584,
        0.98196204,  0.44196924])
>>> print(tr.stats)
         network: BW
         station: RJOB
        location:
         channel: EHZ
       starttime: 2009-08-24T00:20:03.000000Z
         endtime: 2009-08-24T00:20:32.990000Z
   sampling_rate: 100.0
           delta: 0.01
            npts: 3000
           calib: 1.0
           ...
>>> tr.stats.starttime
UTCDateTime(2009, 8, 24, 0, 20, 3)
```



### Building a Stream from NumPy Arrays

For ML inference workflows, waveform arrays are often loaded from `.npz` or HDF5 files and converted into ObsPy objects manually.

```python
import numpy as np
from obspy import Stream, Trace, UTCDateTime

# Example shape: (n_samples, 3)
data = np.load("example_trace.npz")
waveforms = data["data"]
dt = float(data["dt"])
channels = data["channels"].split(",")

sampling_rate = 1.0 / dt
starttime = UTCDateTime("2020-01-01T00:00:00")

traces = []
for i, ch in enumerate(channels):
    tr = Trace(data=waveforms[:, i].astype(np.float32))
    tr.stats.channel = ch
    tr.stats.delta = dt
    tr.stats.sampling_rate = sampling_rate
    tr.stats.starttime = starttime
    traces.append(tr)

st = Stream(traces=traces)
```

All traces in a 3-component stream should have:
- identical `starttime`
- identical `npts`
- identical `sampling_rate`
- synchronized indexing across channels

This ensures that predicted phase pick indices correspond to the same physical time across all components.

## Event Metadata

Event metadata are handled in a hierarchy of classes closely modelled after the de-facto standard format [QuakeML](https://quake.ethz.ch/quakeml/). See `read_events()` and `Catalog.write()` for supported formats.

### Event Class Structure

**Hierarchy:** `Catalog` → `events` → `Event` (multiple)

**Event contains:**
- `origins` → `Origin` (multiple)
  - `latitude`, `longitude`, `depth`, `time`, ...
- `magnitudes` → `Magnitude` (multiple)
  - `mag`, `magnitude_type`, ...
- `picks`
- `focal_mechanisms`

## Station Metadata

Station metadata are handled in a hierarchy of classes closely modelled after the de-facto standard format [FDSN StationXML](https://www.fdsn.org/xml/station/) which was developed as a human readable XML replacement for Dataless SEED. See `read_inventory()` and `Inventory.write()` for supported formats.

### Inventory Class Structure

**Hierarchy:** `Inventory` → `networks` → `Network` → `stations` → `Station` → `channels` → `Channel`

**Network:**
- `code`, `description`, ...

**Station:**
- `code`, `latitude`, `longitude`, `elevation`, `start_date`, `end_date`, ...

**Channel:**
- `code`, `location_code`, `latitude`, `longitude`, `elevation`, `depth`, `dip`, `azimuth`, `sample_rate`, `start_date`, `end_date`, `response`, ...

## Classes & Functions

| Class/Function | Description |
|----------------|-------------|
| `read` | Read waveform files into an ObsPy `Stream` object. |
| `Stream` | List-like object of multiple ObsPy `Trace` objects. |
| `Trace` | An object containing data of a continuous series, such as a seismic trace. |
| `Stats` | A container for additional header information of an ObsPy `Trace` object. |
| `UTCDateTime` | A UTC-based datetime object. |
| `read_events` | Read event files into an ObsPy `Catalog` object. |
| `Catalog` | Container for `Event` objects. |
| `Event` | Describes a seismic event which does not necessarily need to be a tectonic earthquake. |
| `read_inventory` | Function to read inventory files. |
| `Inventory` | The root object of the `Network` → `Station` → `Channel` hierarchy. |

## Modules

| Module | Description |
|--------|-------------|
| `obspy.core.trace` | Module for handling ObsPy `Trace` and `Stats` objects. |
| `obspy.core.stream` | Module for handling ObsPy `Stream` objects. |
| `obspy.core.utcdatetime` | Module containing a UTC-based datetime class. |
| `obspy.core.event` | Module handling event metadata. |
| `obspy.core.inventory` | Module for handling station metadata. |
| `obspy.core.util` | Various utilities for ObsPy. |
| `obspy.core.preview` | Tools for creating and merging previews. |



## SeisBench Interoperability Notes

SeisBench models commonly accept ObsPy `Stream` objects directly:

```python
from seisbench.models import PhaseNet

model = PhaseNet.from_pretrained("stead")
annotations = model.annotate(st)
picks = model.classify(st)
```

Before inference:
- ensure traces are time aligned
- ensure channel codes correctly represent horizontal/vertical components
- avoid mixing different sampling rates within one stream
- convert integer waveform arrays to floating point (`float32` is common)
- preserve original timing metadata so predicted sample indices can be converted back to absolute arrival times

When converting predicted times to indices:

```python
pick_idx = int((pick_time - tr.stats.starttime) * tr.stats.sampling_rate)
```

Using incorrect timing metadata or inconsistent component alignment can introduce systematic pick offsets even if the model output probabilities are otherwise reasonable.
