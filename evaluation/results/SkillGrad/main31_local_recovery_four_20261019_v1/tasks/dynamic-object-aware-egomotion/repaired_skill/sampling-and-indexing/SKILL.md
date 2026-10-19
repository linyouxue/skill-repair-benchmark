---
name: sampling-and-indexing
description: "Standardize video sampling and frame indexing so interval instructions and per-frame artifacts stay aligned with a valid key/index scheme."
---

## Plan your index domain (video-frame vs sampled-index)
- Decide which axis your outputs are keyed on:
  - **Video-frame indices**: indices refer to original frames `0..total_frames-1`.
  - **Sampled indices**: indices refer to positions in `sample_ids`, i.e. `0..sample_count-1`.
- Document the choice in one sentence near the output schema, because validation bounds differ.

```python
# sample_ids: increasing list of video-frame indices you will process
sample_ids = make_sample_ids(total_frames)
sample_count = len(sample_ids)
index_domain = "sampled"  # or "video"
max_valid = (sample_count - 1) if index_domain == "sampled" else (total_frames - 1)
```

Decision rule: If the deliverable talks about "sampled frames" or you emit one artifact per sampled step, treat interval endpoints as **sampled indices** unless the task explicitly says otherwise.

## Build sampling IDs once and reuse everywhere
- Treat sampling as an explicit **contract**: your `sample_ids` must match the benchmark/task definition (stride-only vs target-fps time grid), not a convenient approximation.
- Generate `sample_ids` in one function and reuse it for every downstream artifact (interval labels, per-sample masks, etc.).
- **Do not append the last frame by default**; only include a terminal “force last frame” sample when the contract explicitly requires it.

```python
import cv2

cap = cv2.VideoCapture(video_path)
meta = {
    "total_frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
    "fps": float(cap.get(cv2.CAP_PROP_FPS)),
}

sample_ids = make_sample_ids(meta)  # implements the contract
assert sample_ids == sorted(set(sample_ids)) and sample_ids[0] == 0
# Downstream code iterates over enumerate(sample_ids)
```

Read references/target-fps-sampling-contract.md when the task states a target sample rate (e.g., “fps=5”) and evaluation depends on matching the sampler.
Skip when the task provides an explicit `sample_ids` list or explicit frame numbers.

## Interval keys: default to inclusive endpoints
- Use strict key format `"{start}->{end}"` with integers only.
- Unless a task specifies half-open ranges, interpret **both `start` and `end` as valid indices** on your chosen index domain (inclusive).
- When compressing per-index labels, emit `end_inclusive` as the last index in the run (so the last interval ends at `max_valid`, not `max_valid+1`).

```python
runs = []  # list of (start, end_inclusive, value)
start = 0
for i in range(1, N):
    if values[i] != values[i-1]:
        runs.append((start, i - 1, values[i-1]))
        start = i
runs.append((start, N - 1, values[N - 1]))
interval_dict = {f"{s}->{e}": v for (s, e, v) in runs}
```

Read references/interval-coverage-validation.md when you generate interval-compressed keys from per-frame/per-sample sequences.
Skip when outputs are already per-index (no interval compression).

## Common Pitfalls
- Mixing index domains (validating sampled-index intervals against `total_frames`, or vice versa) so an out-of-range endpoint slips through.
- Using half-open interval compression (`start->next_start`) when the consumer expects endpoints to be valid indices (inclusive).
- Choosing a sampling policy ad hoc (e.g., stride + “append last frame”) so your sampled-index space no longer matches the benchmark’s sampler.
- Creating `sample_ids` in one place but iterating a different length elsewhere (off-by-one between labels, masks, and instructions).
