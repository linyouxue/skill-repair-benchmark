# Test-First Dependency Setup For Research Repos (PEP 668 Safe)

## Purpose
Make an unfamiliar research repository runnable by driving environment setup from the repo's actual execution signal (unit tests or provided entrypoints), while adapting to sandbox constraints (for example PEP 668) and avoiding brittle tool/version prescriptions.

## When to Use
Use this when you need to reproduce results or pass repo-provided tests in an unknown environment, especially when dependency installation may be constrained (externally managed Python, missing conda/venv permissions) and the acceptance criteria is a test run or exact numeric assertions.

## Procedure
- 1) Discover the repo's intended run path (no installs yet)
- List dependency declarations and run instructions: check for README, pyproject.toml, requirements*.txt, environment*.yml, setup.cfg.
- Discover how to run verification: look for CI config, Makefile targets, tox, nox, pytest configuration, or a tests/ directory.
- 2) Execution anchor: run-first preflight to learn what is missing
- Choose the most direct verifier-like command available (prefer: existing unit tests; else the repo's documented minimal run).
- Run it once in the current environment to surface missing modules or tooling (do not "fix" anything yet).
- Record the exact command used and the first failure cause (missing import/package vs. runtime assertion/numeric mismatch).
- 3) Decide the lightest viable install route by capability detection
- Check whether you can create an isolated environment:
- If venv creation is allowed, prefer a venv and install inside it.
- If the system is externally managed (PEP 668) and venv is blocked/unavailable, do not fight the system; plan for a constrained install (for example, user-site) consistent with the environment rules.
- If conda/mamba is available and the repo provides an environment file, use that; otherwise do not introduce it.
- Install only what the preflight failure indicates is required to run the chosen command (start with the first missing dependency chain).
- 4) Iterate with bounded fallback and checkpoints (smallest change, re-run)
- Install dependencies using the repo-declared files when possible (prefer pinned constraints already present in the repo).
- After each install batch or code change, rerun the exact same command from step 2.
- If an install attempt fails due to environment/tool constraints, take one bounded fallback step in this order, then re-run the smallest check:
- Try the repo's preferred method (pyproject/requirements/environment file) using the currently active Python.
- If blocked by externally managed Python, use an isolated env if available; otherwise use the least-invasive environment-supported install mode (for example, user-site) while keeping installs minimal.
- Only if the repo explicitly requires a different Python AND you can create a new interpreter safely in this environment, switch; otherwise stop and request clarification.
- Stop iterating once the command passes, then rerun from a clean shell/session to confirm reproducibility.

## Constraints / Pitfalls
- Do not perform major environment rebuilds (new interpreter toolchains, containerization, or multi-step bootstraps) unless the preflight run proves it is necessary (for example, an explicit Python-version requirement that blocks execution) and the environment supports it.
- Do not add "optional" algorithmic branches (for example label smoothing, hinge variants, third-party library parity modes) unless they are explicitly required by repo configuration or a failing test; implement the simplest spec that makes the existing tests pass, and validate by rerunning the same test command.