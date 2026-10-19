# Target-FPS sampling contract (time-grid → frame indices)

Use this when a task/benchmark specifies a target sampling rate (e.g., “fps = 5”) and your downstream artifacts are keyed by sampled index (interval JSON, per-sample masks, etc.). The goal is to make `sample_ids` match the evaluator’s sampler and to **avoid ad-hoc fixes** like “append the last frame” unless the spec requires it.

## Procedure

### 1) Capture metadata and choose the contract branch
You need: `src_fps`, `total_frames`, and either `duration_sec` or a way to compute it.

Runtime branch:
- **Branch A (time-grid contract)**: “sample at 5 fps” means sample times `t_k = k / 5` over the video duration.
- **Branch B (stride-only contract)**: “every Nth frame” or “step = round(src_fps/5)” with no mention of time grid.

```python
import math

def sampling_contract(src_fps: float, total_frames: int, target_fps: float, mode: str):
    assert total_frames >= 1 and src_fps > 0 and target_fps > 0
    duration_sec = total_frames / src_fps

    if mode == "time_grid":
        # sample at exact times; do not include t==duration by default
        K = int(math.floor(duration_sec * target_fps + 1e-9)) + 1  # includes k=0
        times = [k / target_fps for k in range(K) if (k / target_fps) < duration_sec]

        # Mapping rule: MUST match spec; pick one and stick to it.
        def t_to_idx(t):
            return int(round(t * src_fps))

        ids = [min(total_frames - 1, max(0, t_to_idx(t))) for t in times]
        # Deduplicate (can happen due to rounding) while keeping order
        out = []
        for i in ids:
            if not out or out[-1] != i:
                out.append(i)
        return out

    if mode == "stride_only":
        step = max(1, int(round(src_fps / target_fps)))
        return list(range(0, total_frames, step))

    raise ValueError(f"Unknown mode: {mode}")
```

### 2) Terminal-sample rule (explicit, not implicit)
Runtime branch:
- If the spec explicitly says “include last frame” / “ensure final sample is the last frame”, then append it.
- Otherwise, **do not append**; let the sampler define the terminal sample.

```python
def maybe_force_last(sample_ids, total_frames: int, force_last: bool):
    if force_last and sample_ids and sample_ids[-1] != total_frames - 1:
        return sample_ids + [total_frames - 1]
    return sample_ids
```

### 3) Verification: compare against the intended contract and fail fast
Verification should catch: extra terminal sample, wrong cadence, or mismatched count.

```python

def verify_sampling(sample_ids, expected_ids, *, context: str = ""):
    if sample_ids != expected_ids:
        # Action on failure: treat sampling as the root cause and fix it before generating outputs.
        extra = [i for i in sample_ids if i not in set(expected_ids)]
        missing = [i for i in expected_ids if i not in set(sample_ids)]
        raise AssertionError(
            f"Sampling mismatch {context}:\n"
            f" expected_count={len(expected_ids)} got_count={len(sample_ids)}\n"
            f" expected_tail={expected_ids[-5:]} got_tail={sample_ids[-5:]}\n"
            f" extra={extra[:10]} missing={missing[:10]}\n"
            "Corrective action: re-derive sample_ids from the spec (time-grid vs stride-only) and rerun downstream generation."
        )

# Example usage (you must choose mode/rounding rule per spec)
expected = sampling_contract(src_fps, total_frames, target_fps=5.0, mode="time_grid")
actual = sampling_contract(src_fps, total_frames, target_fps=5.0, mode="time_grid")
verify_sampling(actual, expected, context="time_grid")
```

## Notes / decision guidance
- If the task says “fps=5” but also supplies an exact reference sampler or expected count, treat that as authoritative.
- If rounding rule is unspecified, pick one (round vs floor) and validate against any provided examples; otherwise, your best defense is to build the sampler in one place and make mismatches obvious early.
