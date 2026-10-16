# Reproduce CI in an evaluator-equivalent environment

Use this when local reproduction is flaky or when CI uses older/newer tooling than your default environment.

## Procedure

1. Extract boundary facts from logs/config:
   - install command(s)
   - toolchain versions (Python, pip, setuptools/wheel/build backend)
   - test command(s)
2. Create a clean venv/container and pin those versions.
3. Run the exact install, then the exact tests.
4. Only after you can reproduce locally, start patching.

```python
import subprocess
import sys


def run(cmd: str) -> None:
    subprocess.check_call(cmd, shell=True)


def reproduce(install_cmd: str, test_cmd: str) -> None:
    # Branch A: fresh environment (recommended)
    if sys.prefix == sys.base_prefix:
        raise RuntimeError("Not in a venv; create an isolated environment first")

    run(install_cmd)
    run(test_cmd)


# Example usage: fill in with the evaluator’s commands
# reproduce("python -m pip install -e '.[dev]'", "python -m pytest")
```

## Runtime branches

- If you *cannot* pin tool versions (e.g., restricted runner): reproduce using a container image that matches CI and run commands inside it.
- If install succeeds but tests fail: treat it as a runtime/test problem; stop modifying packaging and move to code-level diagnosis.

## Verification

Re-run the boundary in a **newly created** clean environment.

- If the boundary still fails: collect the exact stderr/stdout, confirm tool versions (`python -m pip --version`, `python -c 'import setuptools; print(setuptools.__version__)'`), then repeat the reproduction procedure with corrected pins.
- If the boundary passes: stop and avoid additional unrelated changes; prepare the minimal diff for submission.
