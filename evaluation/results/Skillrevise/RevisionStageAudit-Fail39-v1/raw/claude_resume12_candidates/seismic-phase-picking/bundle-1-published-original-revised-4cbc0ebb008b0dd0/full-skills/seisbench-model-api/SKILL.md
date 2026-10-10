# SeisBench Phase Picking Workflow

## Purpose
Executable recipe for extracting P and S phase picks from seismic waveforms (typically stored as NPZ arrays) using SeisBench pretrained models, returning zero-or-more integer sample indices per phase per trace, aligned with the original (pre-resampling) sampling grid.

## When to Use
Use when the task is phase picking from waveform arrays (e.g., NPZ files containing channel data plus `dt` or `sampling_rate`) and the expected output is sample indices of P and S arrivals per trace. Do not use for denoising, magnitude estimation, or depth phases; and do not use when input is already pick-time metadata.

## Procedure
- Discover inputs: inspect the NPZ keys and metadata. Record `original_sampling_rate = 1.0 / dt` (or the stored `sampling_rate`), channel count/order, and trace length `n_samples`. If channel order is unknown, assume Z,N,E and verify by trying both orderings on a sample and comparing pick confidences.
- Build an ObsPy `Stream`: wrap each channel as a `Trace` with `stats.sampling_rate = original_sampling_rate`, `stats.starttime = UTCDateTime(0)`, and distinct `stats.channel` codes (e.g., `HHZ`,`HHN`,`HHE`). Group all channels of one event into one Stream.
- Scale guard: compute `s = max(abs(data)).` or `data.std()` across channels. If `s < 1e-6`, multiply all channel data by `1.0 / max(s, 1e-30)` so std is near 1 before passing to the model. Do not clip.
- Load the model once: `model = seisbench.models.PhaseNet.from_pretrained("original")` (or `"stead"` as fallback). Move to GPU if available. Choose `P_threshold` and `S_threshold` (start at 0.3 and 0.3) and tune on a held-out subset by sweeping in {0.1, 0.2, 0.3, 0.5}.
- Pick extraction: call `picks, *_ = model.classify(stream, P_threshold=P_threshold, S_threshold=S_threshold, batch_size=...)`. For each returned pick, compute `idx = int(round((pick.peak_time - trace.stats.starttime) * original_sampling_rate))` where `trace` is the matching channel. Keep picks with `0 <= idx < n_samples` and label by `pick.phase` (`"P"` or `"S"`).
- Verify: assert that output per trace is a (possibly empty) list of P indices and a (possibly empty) list of S indices, all integers in `[0, n_samples)`. If `annotate` is used instead, read channels named ending in `_P` and `_S`, run peak detection (e.g., `scipy.signal.find_peaks` with `height=threshold`, `distance=sampling_rate*1.0`), and convert peak sample indices back to the original grid using the annotation trace's own `sampling_rate` ratio.

## Constraints / Pitfalls
- Do NOT force exactly one P and one S per trace. The contract permits zero or many; argmax-based single-pick strategies lose F1 on noise-only or multi-event traces.
- Convert pick times to indices using the original trace's `starttime` and `original_sampling_rate`, not the resampled annotation stream's grid; mixing grids produces off-by-many-samples errors.
- Do not hardcode thresholds; tune on validation data and keep per-phase thresholds separate.
- Do not segment the waveform manually; SeisBench handles windowing. Pass the full trace.
- Do not reuse the rescaling factor across traces; compute per-trace.
- Avoid loading models inside loops; instantiate once and reuse.