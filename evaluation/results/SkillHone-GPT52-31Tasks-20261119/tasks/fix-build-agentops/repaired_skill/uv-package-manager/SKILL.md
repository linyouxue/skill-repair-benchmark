---
name: uv-package-manager
description: Practical uv patterns for creating venvs, installing deps, and running commands. Use when you need fast, reproducible Python environment setup.
---

# uv package manager (practical guide)

This skill is intentionally **concise** when preloaded. For the full reference, load:
- `resources/full-guide.md`

## Default workflow (recommended)

```bash
# Create (or reuse) a project venv
uv venv

# Install project deps from pyproject/lock
uv sync

# Run commands inside the venv (no activation needed)
uv run pytest
uv run python -m pip --version
```

## Common patterns

### Install a project

- Prefer **non-editable** installs in CI unless you need editable behavior:

```bash
uv pip install .
```

- Editable installs:

```bash
uv pip install -e .
```

### Add dependencies

```bash
uv add requests
uv add --dev pytest
```

### Reproducible CI

```bash
# If a lockfile exists
uv sync --frozen
```

## Troubleshooting (high-signal)

- If installs fail due to permission errors in user-site locations, prefer a project venv and use `uv run ...`.
- If a project’s packaging/build backend is incompatible with editable installs, try a non-editable install first; then consider a virtualenv with newer pip/setuptools.

