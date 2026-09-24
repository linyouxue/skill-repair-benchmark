---
name: uv-package-manager
description: Use uv to install dependencies and run project commands/tests in a reproducible
  environment.
---

## Steps
1. Install/sync dependencies (as the project requires), typically:
   - `uv sync` (optionally `--all-extras --dev` if used by the repo).
2. Run commands without manual venv activation using `uv run ...` (e.g., `uv run pytest`).
3. For debugging, run tests with tighter feedback loops:
   - `uv run pytest -x` to stop on first failure.
   - `uv run pytest path/to/test_file.py -k test_name` for focused iteration.
4. After fixes, run the full test suite via `uv run pytest` to confirm the build is green.
## Expected Result
Consistent installs and test runs that match CI behavior, enabling quick iteration and reliable verification.
