---
name: output-validation
description: "Validate that produced deliverables match required schemas and an exact output allowlist, catching format, range, consistency, and extra-artifact manifest failures before submission."
---

# When to use
- After generating outputs (interval instructions, masks, etc.), before submission/hand-off.

## Workflow: validate against an allowlist of deliverables
1) Identify the exact required output paths (filenames + directories) and treat them as an **allowlist**.
2) While implementing, avoid writing any other artifacts in the task workspace (debug images, logs, checkpoints).
3) If diagnostics are needed, keep them in-memory or write only to a guaranteed-ignored temp location outside tracked outputs.
4) Before finishing, verify the output inventory contains **only** the allowlisted deliverables.

Read references/output-inventory-cleanliness.md when the evaluator enforces an exact output manifest (extra files/dirs cause failure even if deleted later). Skip when extra artifacts are explicitly allowed.

## Checks (schema + consistency)
- **Key format**: every key is `"{start}->{end}"`, integers only, `start<end` for half-open ranges (or `start<=end` for inclusive-end ranges).
- **Index-space declaration**: explicitly lock `index_space` (sample vs video) and `end_semantics` (half-open vs inclusive) from prompt/evaluator evidence before generating *or validating* keys.
- **Index-space bounds**: validate keys against the declared domain (`n_frames` for video space, `num_samples` for sample space), not against a convenient proxy like `<= num_samples`.
- **Conversion correctness**: when labels are computed per-sample but output keys must be video-frame indexed, compress in sample space then convert runs using `sample_ids`; re-run bounds + coverage checks in video space.
- **Coverage**: intervals cover the intended domain (all samples or all frames required), with no gaps/overlaps beyond the declared semantics.
- **Sampling policy conformance**: if the prompt defines sampling as “X fps”, verify `sample_ids` follow the fixed frame-step convention (`step_frames = max(1, round(video_fps / sample_fps))`) and that spacing is uniform (allow only an optional final `n_frames-1` append) before emitting any per-sample artifacts or interval keys.
- **Frame count**: NPZ `f_{i}_*` count equals `num_samples`; no gaps or missing components.
- **CSR integrity**: each frame has `data/indices/indptr`; `len(indptr)==H+1`; `indptr[-1]==indices.size`; indices within `[0,W)`.
- **Value validity**: JSON values are non-empty string lists; labels in the allowed set.

Read references/interval-keys-index-space.md when interval-key validation is failing or ambiguous (e.g., whether keys should be sample-indexed vs video-frame-indexed, or half-open vs inclusive). Skip when outputs contain no interval-keyed artifacts.

# Reference snippet
```python
import json, numpy as np
from pathlib import Path

def parse_interval_key(k: str):
    s, e = k.split("->")
    if not (s.isdigit() and e.isdigit()):
        raise ValueError(f"Bad interval key: {k}")
    return int(s), int(e)

def validate_outputs(*, allowed_paths, instructions_path, masks_path,
                     video_meta, index_space: str, end_semantics: str, num_samples: int,
                     video_fps: float, sample_fps: float, sample_ids):
    allowed = {Path(p) for p in allowed_paths}
    found = {Path(instructions_path), Path(masks_path)}
    assert found.issubset(allowed)

    # Sampling policy conformance (fixed frame-step).
    step_frames = max(1, round(video_fps / sample_fps))
    core = sample_ids[:-1] if (len(sample_ids) >= 2 and sample_ids[-1] == (int(video_meta["frames"]) - 1) and (sample_ids[-1] - sample_ids[-2]) != step_frames) else sample_ids
    assert all(b - a == step_frames for a, b in zip(core, core[1:])), "non-uniform sample spacing"

    j = json.load(open(instructions_path))
    npz = np.load(masks_path)

    n_frames = int(video_meta["frames"])
    H = int(video_meta["H"]); W = int(video_meta["W"])
    domain = num_samples if index_space == "sample" else n_frames

    max_end = -1
    for k, v in j.items():
        s, e = parse_interval_key(k)
        if end_semantics == "half-open":
            assert 0 <= s < e <= domain
            max_end = max(max_end, e)
        else:  # inclusive-end
            assert 0 <= s <= e < domain
            max_end = max(max_end, e)
        assert isinstance(v, list) and v and all(isinstance(lbl, str) for lbl in v)

    # Coverage cross-check (full-domain tasks)
    if end_semantics == "half-open":
        assert max_end == domain
    else:
        assert max_end == domain - 1

    assert npz["shape"][0] == H and npz["shape"][1] == W
    indptr = npz["f_0_indptr"]; indices = npz["f_0_indices"]
    assert indptr.shape[0] == H + 1 and indptr[-1] == indices.size
    assert indices.size == 0 or (indices.min() >= 0 and indices.max() < W)
```

# Common Pitfalls
- **Proxy-domain validation**: validating interval endpoints against `num_samples` by default can mask a wrong `index_space`; always validate against the declared domain and run a coverage check in the same convention.
- **Non-deterministic sampling**: time-rounding/floor-based index derivation can create irregular spacing; prefer a fixed frame-step sampling policy and audit arithmetic progression.
- **Manifest violations**: creating extra debug/intermediate files in the workspace can fail exact-manifest evaluators even if you delete them later.

# Self-check list
- [ ] Deliverables match the required allowlist; no extra files/dirs were created in tracked locations.
- [ ] Sampling policy matches the declared convention (fixed `step_frames`), not a time-rounding/floor scheme.
- [ ] Index space + interval semantics were declared and used for both emission and validation.
- [ ] If labels were per-sample but output keys are video-space, runs were converted via `sample_ids` and re-validated against `n_frames`.
- [ ] JSON keys/values pass format + bounds checks in the correct domain.
- [ ] Interval coverage matches the convention (`max_end` vs `domain` for full coverage).
- [ ] NPZ frame count matches `num_samples`; keys consecutive.
- [ ] CSR structure and `shape` validated.
