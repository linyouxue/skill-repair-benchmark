---
name: nlp-research-repo-package-installment
version: "1.6"
description: Align Python version and repo-declared dependencies (requirements.txt / environment.yml) before installing packages for NLP research code reproduction.
---

# NLP Research Repo Package Installment

When reproducing an NLP research repo, **align the environment to the repo’s declared dependencies first**. The most common causes of non-reproducible results are:

- **Python version mismatch** (e.g., repo pins Python 3.10 but the machine has 3.12)
- **Silent dependency drift** (pip installs a different version because the pinned one is incompatible)
- **Installing into the wrong interpreter** (system Python vs the venv you run tests with)

## Checklist (do this before installing anything)

### 1) Locate the repo’s dependency manifests

Look for (in priority order):

- `environment.yml` / `environment.yaml` (often pins Python + has a `pip:` subsection)
- `requirements.txt` / `requirements*.txt`
- `pyproject.toml` (Poetry/uv/pip-tools, etc.)

If both `environment.yml` and `requirements.txt` exist, treat `environment.yml` as the base unless the README says otherwise.

### 2) Extract the required Python version (and watch for PyTorch constraints)

- If the repo pins a **Python major/minor**, match it.
- If the repo pins **torch/transformers/trl**, confirm the pinned versions actually have wheels for that Python.
  - If you install pinned torch on the wrong Python minor, pip may “helpfully” install a different torch version (changing numerics).

### 3) Decide your installation strategy

Preferred order for reproducible research repos:

1. **Create a project venv** (e.g., `<repo>/.venv`) using the correct Python version
2. Use `conda` / `micromamba` if the repo is clearly Conda-first and those tools exist
3. **Last resort**: install into user site-packages with `pip --user` (least reproducible)

## Recommended approach: `uv` (works well without sudo)

`uv` can install specific Python versions and create a venv in a user-writable location.

### Install `uv`

**Preferred (no Python required):**

```bash
# If curl exists
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv --version
```

If `curl` isn’t available, try `wget -qO- https://astral.sh/uv/install.sh | sh`.

If you must use pip (e.g., no curl/wget), install `uv` into the user site:

```bash
# If `python` isn't available, use `python3`.
# If you see PEP 668 / "externally-managed-environment", add `--break-system-packages`.
python3 -m pip install --user -U uv
export PATH="$HOME/.local/bin:$PATH"
uv --version
```

#### If pip fails due to a broken proxy

If you see proxy-related retries or the misleading error `No matching distribution found`, inspect and then retry with proxy env vars disabled:

```bash
env | grep -i -E 'http_proxy|https_proxy|all_proxy|no_proxy' || true

env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY -u all_proxy -u ALL_PROXY \
  python3 -m pip install --user -U uv
```

### Create a venv with the repo’s required Python

```bash
# Replace <PY_VERSION> with the version required by the repo (major.minor[.patch])
uv python install <PY_VERSION>
uv venv --python <PY_VERSION> .venv

# Use the venv Python for all installs/runs
. .venv/bin/activate
python -VV

# Ensure pip exists in the venv:
# - Some minimal images create a venv without pip/ensurepip.
# - If pip is missing, try bootstrapping it first.
python -m ensurepip --upgrade || true
python -m pip --version || true

# Now upgrade packaging tooling (optional)
# NOTE: Some sandboxes have limited/no network. If this fails, keep the bootstrapped pip
# and proceed to install only the repo-pinned packages.
python -m pip install -U pip setuptools wheel || true
```

### Install dependencies (respect pins)

- If the repo uses `requirements*.txt`:

```bash
python -m pip install -r requirements.txt
```

- If the repo uses `environment.yml` **and you don’t have conda**, install from the `pip:` subsection:
  - Copy the `pip:` package list into a requirements file, or install the pinned packages explicitly.

After installation, **verify** key versions:

```bash
python -c "import sys; print(sys.version)"
python -c "import torch; print('torch', torch.__version__)"
```

## Handling PEP 668 / “externally-managed-environment”

Some environments block `pip install` into system Python and display an error like `externally-managed-environment`.

Do this in order:

1. **Use a venv** (preferred): `uv venv ...` or `python -m venv .venv`.
2. If you must install to user site-packages:

```bash
python -m pip install --user <packages>
```

3. Only if still blocked and you understand the tradeoff, add `--break-system-packages` (last resort):

```bash
python -m pip install --user --break-system-packages <packages>
```

## Network / proxy pitfalls (pip/curl/uv)

If `pip install` fails with errors mentioning a proxy, connection resets, or the misleading message `No matching distribution found` / `from versions: none`, it’s often a **network/proxy** issue rather than a real missing package.

1) Inspect proxy environment variables:

```bash
env | grep -i -E 'http_proxy|https_proxy|all_proxy|no_proxy' || true
```

2) Retry the failing command with proxies temporarily disabled:

```bash
env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY -u all_proxy -u ALL_PROXY \
  python -m pip install <packages>
```

Do the same for `curl`/`wget`/`uv` installs if they fail to reach the internet.

Prefer the one-shot `env -u ...` prefix over permanently unsetting variables, so you don’t break internal traffic that truly needs a proxy.

### Common symptom: PyArrow vs NumPy 2.x mismatch

If you see an error like:

- `ImportError: pyarrow requires NumPy 2.0 or newer, found 1.x`

it usually means you installed a newer `pyarrow` wheel while keeping `numpy<2` (or vice versa). Fix by making them compatible:

- Prefer to follow the repo’s pins.
- Otherwise, either upgrade NumPy to `>=2` **or** pin `pyarrow` to a version compatible with your NumPy.

This mismatch can surface indirectly when importing `datasets`.

## When `python -m venv` fails (missing `ensurepip`)

On some minimal Debian/Ubuntu images, creating a venv may fail with an error like:

- `The virtual environment was not created successfully because ensurepip is not available`

Try, in order:

1. If you have sudo: install the OS venv package and retry:

```bash
# Example (version may vary):
sudo apt-get update
sudo apt-get install -y python3-venv
python -m venv .venv
```

2. Use `uv venv` (if you installed `uv`) instead of the stdlib venv.

   Note: some `uv venv` builds may create a venv **without pip**. If `python -m pip` fails inside the venv,
   try:

   ```bash
   . .venv/bin/activate
   python -m ensurepip --upgrade || true
   python -m pip --version
   ```

3. Use `virtualenv` as a user-level fallback.

   If `pip install --user virtualenv` is blocked by **PEP 668** (`externally-managed-environment`), you may need the
   explicit override:

   ```bash
   python -m pip install --user --break-system-packages -U virtualenv
   ```

   If `pip install` is failing due to a proxy, retry with proxies disabled (see “Network / proxy pitfalls”).

   Then create and activate the venv:

   ```bash
   python -m virtualenv .venv
   . .venv/bin/activate
   ```

If pip is blocked by PEP 668, use the guidance in the section above.

## Ensure the `python` command exists (if the task requires it)

Some systems only provide `python3`. If instructions explicitly require `python`, either:

- Use `python3` consistently, **or**
- Create a user-local alias:

```bash
mkdir -p "$HOME/.local/bin"
ln -sf "$(command -v python3)" "$HOME/.local/bin/python"
export PATH="$HOME/.local/bin:$PATH"
python -VV
```

## Reproducibility logging (critical)

Always log the environment from the **exact interpreter** you will use to run the repo (typically the venv Python).

- If the user specifies an output path/name, follow it.
- Otherwise, use a sensible default like `./python_info.txt`.

Example:

```bash
VENV_PY=".venv/bin/python"
"$VENV_PY" -VV > <LOG_PATH>
"$VENV_PY" -m pip freeze >> <LOG_PATH>
```

Tip: if the task asks for a specific file path like `/root/python_info.txt`, don’t improvise a different path/name.

## When exact numeric outputs are graded

If the task expects you to reproduce **exact** tensors / loss values:

- Match the repo’s **Python minor** and pinned dependency versions as closely as possible (even “small” upgrades can change numerics).
- Prefer **CPU** unless the task explicitly requires GPU. Some unit tests auto-select CUDA if available; you can force CPU for reproducibility by running with:

  ```bash
  CUDA_VISIBLE_DEVICES="" python <your_test_or_script.py>
  ```

- Always generate `python -VV` and `pip freeze` logs from the same interpreter you use to run the test.
- If tests fail with `ModuleNotFoundError: No module named '<repo_subdir>'` for imports like `from scripts...`, run from the repo root and set `PYTHONPATH`:

  ```bash
  cd <REPO_ROOT>
  PYTHONPATH=. python path/to/test.py
  ```

  (Prefer `PYTHONPATH=.` over hard-coding absolute paths.)

### Paper-defined losses: turn equations into code (SimPO/DPO-style)

If the task is “implement a loss from the paper” and the output is **numerically graded**, be deliberate about mapping the math to the repo’s tensors:

1) **Find the exact equation** in the paper (or a repo-provided extracted source like `paper.json` / `paper.txt`).
2) **Confirm what the code’s `logps` mean** (sum vs average; includes prompt tokens or only completion tokens).
3) Match the paper’s conventions for:
   - **beta/temperature scaling** (is `beta` multiplying the logit, or folded into the “reward”?)
   - **margins** (`gamma`, and any reparameterization like `gamma / beta`)
   - **label smoothing** (definition varies across codebases)
   - **hinge sign** (usually `relu(margin - score)`)
4) Do a quick **toy sanity check** on 1–2 hand-crafted examples (e.g., if chosen logp > rejected logp, the loss should decrease).

#### SimPO loss quick reference (general)

SimPO commonly uses a reference-free, length-normalized reward based on **average log probability**.
A typical implementation pattern is:

- Inputs: `policy_chosen_logps`, `policy_rejected_logps` (shape `[batch]` or broadcastable)
- Rewards (often for logging):
  - `chosen_reward = beta * policy_chosen_logps`
  - `rejected_reward = beta * policy_rejected_logps`
- Margin: if the config exposes a ratio like `gamma_beta_ratio = gamma / beta`, recover `gamma = beta * gamma_beta_ratio`
- Logits: `(chosen_reward - rejected_reward) - gamma`
- Loss:
  - Sigmoid: `-logsigmoid(logits)` (optionally with label smoothing)
  - Hinge: `relu(-logits)` (equivalently `relu(gamma - (chosen_reward - rejected_reward))`)

Always verify whether the upstream code already computed **average** log probabilities.
If it computed **sums**, divide by the number of non-pad *completion* tokens (not the prompt) to match the “average log probability of a sequence” definition.

## When imports break due to dependency drift

If you hit errors like `ImportError: cannot import name ...` or `ModuleNotFoundError` inside third-party libraries, it’s often because you installed a **different major/minor version** than the repo expects.

Some libraries also have **optional** dependencies that are still imported in common code paths. For example, `trl` trainers may require `rich` even if it’s not explicitly pinned in the repo. If you see `ModuleNotFoundError: No module named 'rich'`, install `rich` (preferably a version compatible with the repo’s `trl`).

Do this in order:

1) Check what’s actually installed:

```bash
# Print the installed version (if the package exposes __version__)
python - <<'PY'
import importlib
pkg = "your_package_name"  # e.g., "trl" or "transformers"
mod = importlib.import_module(pkg)
print(pkg, getattr(mod, "__version__", "unknown"))
PY

python -m pip show your_package_name || true
```

2) Compare against the repo’s pins (`requirements.txt`, `environment.yml`, `pyproject.toml`). If the pins are incompatible with your Python, fix **Python first** (otherwise pip will silently substitute versions).

3) Only as a last resort, add a small compatibility shim (e.g., `try/except ImportError` with a fallback) rather than refactoring large portions of the repo.

## Running tests reliably

- Run from the repo root when imports assume it.
- If a script imports a top-level package that isn’t found (e.g., `from scripts...`), set `PYTHONPATH` to the repo root:

```bash
cd <REPO_ROOT>
PYTHONPATH=. python path/to/script_or_test.py
```

- If you’re running a module (not a file path), prefer `-m`:

```bash
cd <REPO_ROOT>
PYTHONPATH=. .venv/bin/python -m <module.path>
```

## Common failure modes to avoid

- **Wrong Python minor** → pinned wheels unavailable → pip installs different versions → numerics change.
- **Global/user installs** mixed with venv installs → hard to reproduce.
- **Logging `pip freeze` from the wrong interpreter** → the recorded environment doesn’t match the one used for execution.
- **Running tests from the wrong working directory** → imports fail; run from repo root or use `-m`.
