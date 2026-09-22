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



## Validated NPZ Waveform Ingestion

For custom `.npz` traces, validate metadata before constructing ObsPy objects. Require `data`, `dt`, and `channels`; require a finite, two-dimensional numeric array with finite samples, a finite positive scalar `dt`, and a comma-separated channel list whose nonempty labels are unique. Resolve orientation explicitly: prefer `(n_samples, n_channels)`, transpose `(n_channels, n_samples)` when only that interpretation matches, and reject an ambiguous shape rather than guessing. Preserve the original array and column order.

```python
import numpy as np

def load_npz(path):
    with np.load(path, allow_pickle=False) as z:
        missing = {"data", "dt", "channels"} - set(z.files)
        if missing:
            raise ValueError(f"{path}: missing {sorted(missing)}")
        raw = np.asarray(z["data"])
        dt = float(np.asarray(z["dt"]).reshape(()))
        labels = str(np.asarray(z["channels"]).reshape(()).item())
    channels = [x.strip() for x in labels.split(",") if x.strip()]
    if raw.ndim != 2 or not np.issubdtype(raw.dtype, np.number) or not np.isfinite(raw).all():
        raise ValueError(f"{path}: data must be finite numeric 2-D data")
    if not np.isfinite(dt) or dt <= 0 or not channels or len(set(c.upper() for c in channels)) != len(channels):
        raise ValueError(f"{path}: invalid dt or channel labels")
    matches = []
    if raw.shape[1] == len(channels):
        matches.append(raw)
    if raw.shape[0] == len(channels):
        matches.append(raw.T)
    if len(matches) != 1:
        raise ValueError(f"{path}: channel orientation is missing or ambiguous: {raw.shape}")
    return matches[0].astype(np.float64, copy=False), dt, channels
```

For this task, also require exactly three columns after orientation. Skip or diagnose invalid files; do not fabricate `dt`, channel identities, or a time origin.



## Constructing Aligned Traces and Mapping Components

Create one Trace per original column, using the same documented start time and `sampling_rate=1.0/dt` for every component. If acquisition start metadata exists, parse it as `UTCDateTime`; otherwise use a relative origin only for bookkeeping and retain the fact that times are relative.

```python
from obspy import Stream, Trace, UTCDateTime

def as_stream(data, dt, channels, starttime=None):
    start = UTCDateTime(starttime) if starttime is not None else UTCDateTime(0)
    return Stream([Trace(data=data[:, j].copy(), header={
        "channel": name, "starttime": start, "sampling_rate": 1.0 / dt
    }) for j, name in enumerate(channels)])
```

Match component roles from labels, case-insensitively, while preserving the original labels and column mapping. A suffix `Z` is normally vertical; `N`, `E`, `1`, and `2` may identify horizontals when the instrument convention supports it. Use vertical/horizontal features only when the assignment is unique and justified; otherwise retain all channels without inventing a role. For `DPE,DPN,DPZ`, the original columns remain E, N, and Z respectively. Keep a raw array alongside every processed copy. Do not call `remove_response()` unless valid StationXML/Inventory response metadata is available.



## Timing-Safe Preprocessing and Pick Conversion

Preprocess copies, never the source array. Detrending, tapering, robust normalization, and zero-phase filtering preserve the sample grid but can affect edge arrivals; choose filter corners below the per-file Nyquist frequency and use `zerophase=True` when phase timing matters. Avoid causal filters unless their delay is calibrated. Do not resample unless necessary; if resampling or trimming is used, record its rate and origin explicitly.

All reported indices must refer to the untrimmed original array. If a model or detector returns local time `t_local` in a window beginning at original sample `window_offset`, convert once with the original timing: `idx = round(window_offset + t_local / original_dt)` (or, for an absolute time, `round((pick_time - original_starttime) / original_dt)`). For a resampled signal, first convert its local sample/time to seconds, then apply the window offset and original `dt`; do not add a resampled index directly to an original index. Round only at the final conversion, cast to `int`, and bounds-check against the original sample count. A valid pick should satisfy `0 <= idx < n_samples`; discard or diagnose anything outside that range.



## NumPy-Only Fallback and CSV Validation

ObsPy is optional for array-based processing. A NumPy-only implementation can use the validated `(n_samples, 3)` array, the preserved channel map, `dt`, and explicit window/resampling metadata; its detector must still emit indices in original coordinates. Keep separate raw and processed representations so preprocessing cannot silently redefine the index origin.

Before writing `/root/results.csv`, validate every record against the source file: exactly the columns `file_name`, `phase`, and `pick_idx`; phase exactly `P` or `S`; `pick_idx` a finite integer in `[0, n_samples)`; and filename matching the processed input. Remove duplicate phase/index rows if they are accidental, while allowing multiple distinct picks or no pick for a phase. Write the header even when no records are produced, and re-read the CSV to verify schema, integer indices, valid phases, and per-file bounds.
