# Hyperparameter semantics & loss scaling disambiguation

Use this when implementing/modifying an objective and a margin/temperature-like hyperparameter could be interpreted in multiple unit systems (e.g., a config value might store **γ** vs **γ/β**, or a penalty might belong inside vs outside a scaling factor). The goal is to *prove* which algebra the repository expects before you commit to one.

## Decision procedure (repo-first, then math)

### 1) Gather repo-wide evidence

- Find every place the hyperparameter is set (configs, scripts, CLI flags) and record typical numeric values.
- Find every place it is used in code and note whether it is multiplied/divided by other scalars.

```python
import re
from pathlib import Path

name = "some_margin_name"
root = Path(".")

def grep_text(paths):
    out = []
    for p in paths:
        s = p.read_text(errors="ignore")
        for i, line in enumerate(s.splitlines(), 1):
            if re.search(rf"\b{re.escape(name)}\b", line):
                out.append((str(p), i, line.strip()))
    return out

code_hits = grep_text(root.rglob("*.py"))
cfg_hits = grep_text(list(root.rglob("*.yml")) + list(root.rglob("*.yaml")) + list(root.rglob("*.json")))
print("code hits:", code_hits[:10])
print("config hits:", cfg_hits[:10])
```

Runtime branch:
- If configs show values that align with the paper’s γ (direct margin size in logit/reward units), treat the stored value as γ unless the code clearly scales it.
- If configs show values that align with γ/β, treat the stored value as a ratio unless the code clearly rescales it.

### 2) Enumerate plausible algebras with explicit unit interpretations

Write down 2–3 candidates where each is paired with a statement of what the config stores.

Example candidates (use the ones that match your situation):
- **Candidate A**: `logit = beta * delta - gamma` (config stores `gamma`)
- **Candidate B**: `logit = beta * (delta - gamma_over_beta)` (config stores `gamma/beta`)
- **Candidate C**: `logit = beta * (delta - gamma)` (config stores `gamma`, but placed inside scale)

Runtime branch:
- If the config variable name suggests a ratio (e.g., contains “ratio”), do **not** trust the name alone—use it only as a weak prior.
- If code elsewhere already implements one candidate in a tested path, reuse that implementation rather than re-deriving.

### 3) Two-branch numeric check on a fixed mini-batch

Compute the objective/logits under each candidate on the *same* tiny batch and compare to any reference outputs (tests, saved fixtures, known-good trainer) or to invariants (e.g., shift sizes implied by margin).

```python
import torch

torch.manual_seed(0)

beta = torch.tensor(1.0)
delta = torch.randn(8)  # e.g., logp_chosen - logp_rejected (whatever the repo defines)
param = torch.tensor(0.5)  # the config value under test

cand_A = beta * delta - param
cand_B = beta * (delta - param)

# If you suspect param is gamma/beta, also test rescaling:
# cand_A_rescaled = beta * delta - (beta * param)

print("A mean/std:", cand_A.mean().item(), cand_A.std().item())
print("B mean/std:", cand_B.mean().item(), cand_B.std().item())
```

Runtime branch:
- If there is a reference function or existing trainer path: assert that your chosen candidate matches it on the mini-batch.
- If there is no reference: prefer the candidate that makes the margin’s effect consistent with documented ranges (e.g., a margin of 0.5 should shift logits by ~0.5, not ~beta*0.5 unless explicitly stated).

### 4) Verification and corrective action

**Verification:** after implementing the chosen algebra, run whatever check the repo offers (unit test, integration test, or a single forward pass that logs the intermediate logits/losses) and compare against the reference artifact expected by the evaluator.

If verification fails:
1. Re-check step (1) for missed config defaults/overrides (CLI flags, dataclass defaults, hydra composition).
2. Re-run step (3) including the missing candidate(s) (e.g., `gamma = beta * param`) and inspect which one brings outputs closest.
3. Add/adjust an inline comment in code stating the final unit interpretation so future edits don’t drift.
