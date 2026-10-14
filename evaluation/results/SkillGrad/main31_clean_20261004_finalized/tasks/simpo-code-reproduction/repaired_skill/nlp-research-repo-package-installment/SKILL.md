---
name: nlp-research-repo-package-installment
version: "1.3"
description: Reproduce NLP research repos by stabilizing the evaluator entrypoint, matching declared environments, and verifying tensor/hyperparameter semantics before implementing math-heavy objectives.
---

# NLP Research Repo Package Installment

When reproducing an NLP research repo, align the environment to the repo’s declared dependencies first, and treat math-heavy code as an integration task: your “inputs” (tensors, hyperparameters) often have non-obvious semantics.

## Workflow: choose the environment and install path

1. Read dependency specs in this order: `environment.yml`/`.yaml` → `requirements.txt` → `pyproject.toml`/`setup.cfg`.
2. Prefer the repo’s lock/pin strategy (conda env file, constraints file, pinned requirements) over ad‑hoc upgrades.
3. Identify the evaluator entrypoint (test command / script / module) and run everything in a way that makes *that* entrypoint import correctly.
4. Before changing anything, log the current interpreter and packages so you can diff: `python -VV`, `python -m pip --version`, `python -m pip freeze`.
5. If Python major/minor mismatches the repo’s declared range, create a fresh environment that matches (venv/uv/conda).
6. Install in the smallest steps that preserve reproducibility: base deps → repo/package install → optional extras.
7. Gate deep debugging on an entrypoint smoke test: ensure the evaluator command runs far enough to import project modules without ad-hoc edits.
8. After any run that claims to write an artifact (e.g., `*.npz`, `*.json`, checkpoints), immediately verify it exists and inspect keys/shapes/dtypes before iterating.

Read references/evaluator_entrypoint_and_artifact_checks.md when the evaluator fails early with import/path errors (e.g., `ModuleNotFoundError`) or when outputs are saved to disk and must be verified. Skip when the repo is already installed as a package and outputs are in-memory only.

## Operation: create a matching Python environment (uv/venv)

Use this when the repo pins Python or when dependency resolution is brittle.

```bash
python -VV
python -m venv .venv
. .venv/bin/activate
python -m pip install -U pip setuptools wheel
python -m pip install -r requirements.txt
```

Decision rule: if installs fail with ABI/build errors (torch, tokenizers), switch to the repo’s intended Python version and/or a conda-based setup.

## Operation: verify dependency semantics before implementing math-heavy code

When re-implementing a paper’s objective inside a repo, verify that the tensors you consume (e.g., `*_logps`) and the hyperparameters you apply (e.g., margins, temperatures) have the same semantics/units as the paper *and* the repo.

Minimum checks before you commit an algebra:

1. **Repo-wide evidence:** search for the tensor/hparam name in configs, scripts, and docs; read surrounding comments/docstrings and record intended units and typical numeric ranges.
2. **Producer contract:** trace any ambiguous tensors (e.g., `*_logps`) back to the function that creates them and read its normalization/masking contract.
3. **Scale-placement disambiguation:** if a term could plausibly be inside vs outside a scale factor (e.g., `β*(Δ-γ/β)` vs `β*Δ-γ`), enumerate the plausible forms and tie each to a concrete interpretation of the config value’s units.
4. **Two-branch numeric check:** when ambiguity remains, compute a tiny batch both ways and check which branch matches any existing trainer/tests *or* matches the repo’s documented hparam ranges (the wrong branch often yields logits that are off by a constant factor).
5. **Document the decision:** add an inline comment stating the chosen units (e.g., “`gamma` is in logit units; do not multiply by `beta`”) and avoid multiplying/dividing by `beta` unless the repo explicitly stores a ratio.

```python
import re
from pathlib import Path

names = ["some_hparam_name", "some_tensor_name"]
for name in names:
    paths = [str(p) for p in Path(".").rglob("*.py")
             if re.search(rf"\b{re.escape(name)}\b", p.read_text(errors="ignore"))]
    print(name, "hits:", paths[:8])
```

Decision rule: if an input is ambiguous (sum vs mean, includes prompt tokens vs response-only, margin γ vs γ/β), stop and determine its producer and units before writing equations.

Read references/logp_tensor_semantics.md when implementing an objective that uses provided `*_logps`-like tensors and the paper uses length normalization (or masking). Skip when the `*_logps` producer is in the same file/function and its normalization is unambiguous.

Read references/hparam_semantics_loss_scaling.md when implementing or modifying a loss/objective and a config parameter’s meaning could be γ vs γ/β (or inside vs outside a scale factor). Skip when the repo already has a tested reference function you can call directly.

## Common Pitfalls

- Installing packages before checking Python version pins (leads to unfixable ABI conflicts).
- Mixing conda and pip installs without understanding which packages must come from which solver.
- Upgrading core libraries (torch/transformers) beyond the repo’s declared range to “fix” an import error.
- Debugging model math before the evaluator entrypoint can import and run end-to-end.
- Claiming an output artifact exists without immediately checking it on disk (path, keys, shapes, dtype).
- Implementing a loss directly from the paper while assuming tensor semantics (e.g., `*_logps` sums vs per-token averages, mask conventions).
- Implementing a loss/objective without validating the repo’s hyperparameter semantics/units (terms placed inside vs outside scaling factors).
