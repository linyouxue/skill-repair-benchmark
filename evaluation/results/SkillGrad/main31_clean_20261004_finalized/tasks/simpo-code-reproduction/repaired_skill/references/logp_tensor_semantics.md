# Log-prob tensor semantics for length-normalized objectives

Use this when a paper’s objective defines rewards/logits using a *length-normalized* log-probability (e.g., \(\tfrac{1}{|y|}\log\pi(y\mid x)\)) but the codebase hands you tensors named like `*_logps`.

## Goal

Determine whether `*_logps` are **sequence sums**, **per-token averages**, or **something else** (masking/prompt-included), and then implement the paper’s formula exactly once (no missing or double normalization).

## Procedure

### 1) Find the producer and read its contract

Search for the function that creates the tensor (often something like `get_*logps`, `compute_logprobs`, `score_sequences`). Read its docstring and arguments (look for `average_log_prob`, `normalize`, `mask`, `prompt_length`).

```python
import re
from pathlib import Path

def find_symbol(sym: str):
    out = []
    for p in Path(".").rglob("*.py"):
        s = p.read_text(errors="ignore")
        if re.search(rf"\b{re.escape(sym)}\b", s):
            out.append(str(p))
    return out

for sym in ["get_batch_logps", "average_log_prob", "logps"]:
    print(sym, find_symbol(sym)[:5])
```

### 2) If the contract is unclear, infer by a numeric check

A sum should roughly scale with length; an average should not.

```python
import torch

def classify_logps(logps: torch.Tensor, lengths: torch.Tensor) -> str:
    # lengths: (B,) count of response tokens included in logps
    # Heuristic: if |logps| correlates with lengths, it's likely a sum.
    corr = torch.corrcoef(torch.stack([logps.float().abs(), lengths.float()]))[0, 1]
    return "sum-like" if corr > 0.5 else "avg-like"

B = 4
logps = torch.randn(B)
lengths = torch.randint(5, 50, (B,))
print("classification:", classify_logps(logps, lengths))
```

Runtime branch:
- If `sum-like`: treat `*_logps` as \(\log\pi(y\mid x)\) and divide by the **true included-token count** before applying any scaling factor \(\beta\).
- If `avg-like`: treat `*_logps` as \(\tfrac{1}{|y|}\log\pi\) and do **not** renormalize.

### 3) Compute correct lengths (the common footgun)

Lengths must match *exactly* which tokens were included by the log-prob producer (response-only vs prompt+response; masked padding excluded).

```python
import torch

def response_lengths(attention_mask: torch.Tensor, prompt_mask: torch.Tensor | None = None) -> torch.Tensor:
    # attention_mask: 1 for real tokens, 0 for padding
    # prompt_mask: 1 for prompt tokens, 0 otherwise (optional)
    if prompt_mask is None:
        return attention_mask.sum(dim=1)
    return (attention_mask * (1 - prompt_mask)).sum(dim=1)

attn = torch.tensor([[1, 1, 1, 0], [1, 1, 0, 0]])
prompt = torch.tensor([[1, 1, 0, 0], [1, 0, 0, 0]])
print(response_lengths(attn, prompt))
```

### 4) Verification (must pass before you trust the loss values)

After implementing the objective, validate the semantics:

1. **Sanity:** If you switch between sum and avg interpretations (by multiplying/dividing by lengths), the loss should change in a predictable direction (longer sequences are most affected).
2. **Invariants:** If you duplicate a response token sequence (same tokens repeated) and recompute logps, the *average* version should be similar while the *sum* version roughly doubles in magnitude.

Corrective action on failure:
- If tests/snapshots still mismatch: re-check (a) whether prompt tokens are included, (b) whether the producer already divides by length, and (c) whether label smoothing or temperature/β is applied inside vs outside the logit.
- If your computed lengths differ from what the producer uses: refactor to reuse the same mask/length computation as the producer function (single source of truth), then rerun verification.
