---
name: obspy-data-api
description: Create and manipulate ObsPy `Stream`/`Trace` objects (incl. correct timing
  metadata) from waveform arrays so SeisBench models and signal-processing utilities
  work reliably.
---

## Steps
1. For each 3‑component waveform `data` shaped `(n_samples, 3)` and sampling interval `dt`, build one `Trace` per channel with `trace.data = data[:, i].astype(np.float32)`.
2. Set timing metadata on each trace: `tr.stats.delta = dt`, `tr.stats.sampling_rate = 1.0 / dt`, `tr.stats.npts = n_samples`.
3. Set consistent `tr.stats.starttime` (e.g., `UTCDateTime(0)` for all traces) so any SeisBench annotation timestamps can be converted back to sample indices via `(pick_time - starttime) * sampling_rate`.
4. Combine traces into a single `Stream` for the station/trace file (3 traces total), and keep channel codes from the file’s `channels` field.
## Expected Result
A valid ObsPy `Stream` with correct `starttime` and `sampling_rate`, enabling robust time↔index conversion and downstream SeisBench inference.
