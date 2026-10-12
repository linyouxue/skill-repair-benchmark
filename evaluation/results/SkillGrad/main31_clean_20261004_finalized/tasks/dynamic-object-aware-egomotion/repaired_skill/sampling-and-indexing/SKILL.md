---
name: sampling-and-indexing
description: "Standardize video sampling and frame indexing so interval instructions and per-sample artifacts share the same declared index space and interval semantics."
---

# When to use
- You need to choose a sampling policy and ensure *all downstream outputs* (interval instructions, per-sample masks, etc.) are indexed and validated in the same **index space**.

## Workflow: declare index space + end semantics, then lock before compression
1) Read video metadata (frame count, fps, resolution) and compute `sample_ids`.
2) **Declare the index space used by interval keys**:
   - **Video-frame index space**: endpoints refer to original frame numbers.
   - **Sample-index space**: endpoints refer to positions in `sample_ids` (0..num_samples-1).
3) **Declare end semantics implied by prompt/examples** (commonly half-open).
4) If labels are computed per-sample but keys must be in **video-frame** space, **compress in sample space first**, then convert runs using `sample_ids` before writing.
5) Validate bounds and coverage against the same declared domain; do not validate video-space keys against `num_samples` by accident.

Read references/interval-keys-index-space.md when emitting `start->end` interval keys and either (a) the evaluator is failing despite schema-like JSON or (b) you have `sample_ids` plus `n_frames` and must decide sample vs video index space. Skip when outputs are per-sample arrays only (no interval keys).

## Core sampling pattern (video_fps + sample_fps → sample_ids)
```python
import cv2

def choose_sample_ids(video_path: str, *, video_fps: float, sample_fps: float):
    # Deterministic frame-step policy: fixed step in frames.
    step_frames = max(1, round(video_fps / sample_fps))

    cap = cv2.VideoCapture(video_path)
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    sample_ids = list(range(0, n_frames, step_frames))
    if sample_ids and sample_ids[-1] != n_frames - 1:
        sample_ids.append(n_frames - 1)

    # Self-check: arithmetic progression + optional last-frame append.
    core = sample_ids[:-1] if (len(sample_ids) >= 2 and sample_ids[-1] == n_frames - 1 and (n_frames - 1 - sample_ids[-2]) != step_frames) else sample_ids
    assert all(b - a == step_frames for a, b in zip(core, core[1:])), "non-uniform sample spacing"
    assert sample_ids == sorted(set(sample_ids)) and all(0 <= i < n_frames for i in sample_ids)

    return n_frames, step_frames, sample_ids
```

Decision rule: when sampling is specified as “X fps”, do **not** back-compute a sample count from duration/time and then `floor(...)` indices; use a fixed `step_frames` and audit spacing.

## Self-check list
- [ ] `sample_ids` strictly increasing, all `< n_frames`.
- [ ] Gaps follow a fixed `step_frames` (allow only an optional final `n_frames-1` append).
- [ ] Interval keys were generated in the declared `index_space` and validated against its domain.
- [ ] Interval keys follow the declared `end_semantics` and pass a coverage check (`max_end` vs domain).
- [ ] When emitting video-frame interval keys from per-sample labels, runs were converted via `sample_ids` *after* compression and re-validated against `n_frames`.
- [ ] Any per-sample artifact store (e.g., NPZ) contains exactly `num_samples` frames and no extras.
