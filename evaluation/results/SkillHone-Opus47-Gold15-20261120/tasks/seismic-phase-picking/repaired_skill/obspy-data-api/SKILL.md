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

## Building a `Stream` from a NumPy array

When waveform data is supplied as a NumPy array (e.g. from an `.npz` file) rather than as a standard seismological file format, the usual pattern is to build one `Trace` per component and collect them into a `Stream`:

```python
import numpy as np
from obspy import Stream, Trace, UTCDateTime

d = np.load(path, allow_pickle=True)
data = d["data"]                              # shape (n_samples, n_channel_slots)
channels = str(d["channels"]).split(",")      # list of SEED channel codes
dt = float(d["dt"])
starttime = UTCDateTime(str(d["start_time"]))

traces = []
for ch, col in zip(channels, range(len(channels))):
    tr = Trace(data=np.ascontiguousarray(data[:, col]))
    tr.stats.channel = ch
    tr.stats.delta = dt
    tr.stats.starttime = starttime
    traces.append(tr)
st = Stream(traces)
```

The naive form above is only correct when the array column index agrees with the channel-name order. For packed arrays where the number of column slots differs from the number of real components, use the column-mapping logic in the next section.

### Pitfall: component count vs. array column count

A frequent source of *silent* bugs is that the data array may be stored with a **fixed number of channel slots** (often three) regardless of how many real components the station actually recorded. Unused slots are typically zero-padded, and only some of the columns correspond to the component names listed in a `channels`-like field.

For example, with a 3-slot array (`n_samples × 3`) and standard SEED channel codes (the last letter denotes the component: `Z` = vertical, `N`/`1` = north, `E`/`2` = east):

| `channels` field | Likely nonzero columns | Interpretation |
|------------------|-----------------|----------------|
| three codes ending `…E, …N, …Z` | 0, 1, 2 | 3-component station, all slots used |
| one code ending `…Z` | 2 only | vertical-only station (horizontal slots zero) |
| one code ending `…N` | 1 only | single-horizontal station |
| two codes ending `…E, …N` | 0, 1 | 2-component (vertical slot zero) |

Naively iterating with `enumerate(channels)` and reading `data[:, i]` will silently feed all-zero traces into any downstream processing when `len(channels) < data.shape[1]` and the real signal sits in the *last* columns (because the Z component is conventionally stored last). The model then returns a near-constant characteristic function and no picks — which can easily be mistaken for a low-SNR trace.

Always align channel names to the actual data columns. Two robust options:

```python
# Option A: use only columns that carry any signal, in order.
nonzero_cols = [c for c in range(data.shape[1]) if np.any(data[:, c] != 0)]
if len(nonzero_cols) == len(channels):
    col_map = dict(zip(channels, nonzero_cols))
else:
    # Fallback: assume component names fill the last len(channels) columns
    # (i.e. the vertical/Z slot is last by convention).
    col_map = dict(zip(channels,
                       range(data.shape[1] - len(channels), data.shape[1])))

# Option B: use the explicit channel-name suffix (E/N/Z, 1/2/3) to pick the column
#   when the file format documents a fixed slot order.
```

Before trusting a `Stream` built from a packed array, verify per-channel variance (`tr.data.std()` should be non-zero on every real component) and that the channels you expect to see are the channels you actually built. A quick sanity assertion saves a lot of debugging later.

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
