# Interval keys: choosing and validating the index space

Interval-keyed outputs (e.g., JSON maps with keys like `"start->end"`) fail most often when the code silently uses the wrong **index space** (sample indices vs video-frame indices) or the wrong **end semantics** (half-open vs inclusive). This chapter provides a concrete procedure to declare the convention, emit keys accordingly, optionally convert sample-space runs to video-frame runs, and validate them against the correct domain.

## Step 1 — Declare the convention from prompt evidence
Use the prompt’s example/wording to pick both:
- **Index space**
  - `index_space="sample"`: keys refer to the sampled list positions `0..num_samples-1`.
  - `index_space="video"`: keys refer to original frame numbers `0..n_frames-1`.
- **End semantics**
  - `end_semantics="half-open"`: `"i->i+1"` labels exactly one index `i`.
  - `end_semantics="inclusive"`: `"i->i"` labels exactly one index `i`.

Runtime branch: if the prompt is ambiguous, prefer the convention used by any provided validator snippet or example JSON; otherwise choose one convention and add a strict verification check (below) that will fail fast if mismatched.

## Step 2 — Emit single-index and compressed intervals consistently (Python)
```python
from typing import List, Dict, Tuple

def emit_single(i: int, *, end_semantics: str) -> Tuple[int, int]:
    if end_semantics == "half-open":
        return i, i + 1
    return i, i

def compress_labels(label_seq: List[List[str]], *, end_semantics: str) -> Dict[str, List[str]]:
    # label_seq is indexed in the chosen index space already (e.g., per-sample labels).
    out: Dict[str, List[str]] = {}
    run_s = 0
    run_lbl = label_seq[0]
    for i in range(1, len(label_seq) + 1):
        at_end = (i == len(label_seq))
        if at_end or label_seq[i] != run_lbl:
            if end_semantics == "half-open":
                s, e = run_s, i
            else:  # inclusive
                s, e = run_s, i - 1
            out[f"{s}->{e}"] = run_lbl
            if not at_end:
                run_s, run_lbl = i, label_seq[i]
    return out
```

## Step 3 — Runtime branch: convert sample-space runs to video-frame runs
Trigger: you computed labels per-sample, but the required output keys are in **video-frame index space**.

```python
from typing import Dict, List, Tuple

def parse_key(k: str) -> Tuple[int, int]:
    s, e = k.split("->")
    return int(s), int(e)

def sample_runs_to_video(runs: Dict[str, List[str]], *, sample_ids: List[int], end_semantics: str) -> Dict[str, List[str]]:
    # sample_ids maps sample position -> video frame index.
    out: Dict[str, List[str]] = {}
    for k, v in runs.items():
        s, e = parse_key(k)
        if end_semantics == "half-open":
            # sample run [s, e) covers samples s..e-1
            vs = sample_ids[s]
            ve = sample_ids[e - 1] + 1  # keep half-open in video-frame space
        else:
            # sample run [s, e] covers samples s..e
            vs = sample_ids[s]
            ve = sample_ids[e]
        out[f"{vs}->{ve}"] = v
    return out
```

## Step 4 — Validate keys against the correct domain, not a proxy
Runtime branch: bounds depend on both declarations.
```python
def validate_intervals(keys, *, index_space: str, end_semantics: str,
                       num_samples: int, n_frames: int):
    domain = num_samples if index_space == "sample" else n_frames
    max_end = -1
    for k in keys:
        s_str, e_str = k.split("->")
        s, e = int(s_str), int(e_str)
        if end_semantics == "half-open":
            assert 0 <= s < e <= domain
            max_end = max(max_end, e)
        else:
            assert 0 <= s <= e < domain
            max_end = max(max_end, e)
    return max_end, domain
```

## Verification and corrective action
- **Verify**: compute `max_end` and check it matches the declared semantics for full coverage:
  - half-open: expect `max_end == domain`.
  - inclusive: expect `max_end == domain-1`.
- **If verification fails**:
  1) Re-check the prompt example to confirm `index_space` and `end_semantics`.
  2) If the index space is wrong:
     - For per-sample labels but video-frame output, apply `sample_runs_to_video(...)` and then re-validate against `n_frames`.
     - If you accidentally emitted video-frame keys but the evaluator expects sample keys, you must recompress from sample-space labels (do not try to “invert” without a trusted mapping).
  3) If end semantics are wrong, rewrite keys (`i->i` ↔ `i->i+1`) and re-run validation.
