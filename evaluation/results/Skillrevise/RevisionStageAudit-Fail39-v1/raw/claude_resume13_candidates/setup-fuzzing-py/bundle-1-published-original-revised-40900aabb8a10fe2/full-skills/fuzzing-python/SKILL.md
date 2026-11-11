# Python Library Fuzz Driver Authoring

## Purpose
Author one Atheris-based fuzz driver per Python library in a project, run each driver briefly in an isolated environment, capture a libFuzzer log, and verify the log before declaring the artifact complete. The skill encodes an ordered workflow with observable checkpoints and bounded fallbacks for heavy dependencies and library-raised exceptions.

## When to Use
Use when the task requires producing per-library fuzz drivers for a Python repository (one driver per discovered library), each paired with an isolated virtual environment and a captured fuzz run log. Do not use for native-only fuzzing, grammar/protobuf-only fuzzing tasks, or when the task only asks for Atheris API explanation.

## Procedure
- Discover libraries. Enumerate the target libraries from the repository layout (for example top-level packages under the project root). Write the resolved list to `libraries.txt`, one library name per line. Checkpoint: `libraries.txt` is non-empty and each entry corresponds to an importable package directory.
- Analyze each library. For every library, identify a small, importable submodule or public function suitable as a fuzz entrypoint (prefer parsers, decoders, validators, env/config loaders). Record the chosen entrypoint and any dependency concerns in `notes_for_testing.txt` under a per-library section. Checkpoint: each library in `libraries.txt` has a corresponding section in `notes_for_testing.txt`.
- Author `fuzz.py` per library under `<lib>/fuzz.py`. Required template shape:
- `import atheris` and `import sys` at module top.
- `with atheris.instrument_imports():` block that imports the chosen library module(s).
- A `TestOneInput(data: bytes)` function that constructs an `atheris.FuzzedDataProvider(data)` when structured inputs are needed, invokes the target, and wraps the call in `try/except` catching library-declared invalid-input exceptions only (for example `ValueError`, `KeyError`, `UnicodeDecodeError`, `TypeError`, and any library-specific parse/validation error). Do not catch `BaseException` or `Exception` broadly.
- `atheris.Setup(sys.argv, TestOneInput)` then `atheris.Fuzz()`. Checkpoint: `python -c "import ast; ast.parse(open('<lib>/fuzz.py').read())"` succeeds and the file contains `atheris.Fuzz()`.
- Create an isolated environment per library at `<lib>/.venv`. Discover the available tool before committing to a command: check for `uv`, `poetry`, then fall back to the stdlib `python -m venv`. Activate (or invoke the venv's `python`/`pip` directly) and install `atheris` plus the library's declared runtime dependencies (`pyproject.toml`, `requirements*.txt`, or `setup.py`). Checkpoint: `<lib>/.venv/bin/python -c "import atheris, <lib>"` exits 0.
- Fallback for heavy or failing dependencies. If the full install fails, times out, or pulls heavy ML/GPU stacks that are not needed by the chosen entrypoint, narrow the fuzz target to the lightest importable submodule that exercises real parsing/validation code. Record the narrowing (submodule chosen, dependencies skipped, reason) in `notes_for_testing.txt`. Re-run the import checkpoint above against the narrowed target.
- Run the fuzzer. From `<lib>/`, execute the driver with the venv's Python using `-max_total_time=10` (or the time budget declared by the task) and redirect combined stdout+stderr to `<lib>/fuzz.log`. Checkpoint: the process exits on its own within the time budget.
- Verify `fuzz.log`. The log must contain a libFuzzer startup line (for example matching `INFO: Running` or `INFO: Seed`) and at least one progress line containing `exec/s`. The log must not end with an uncaught Python traceback from the driver scaffolding (tracebacks terminating inside `TestOneInput` from an exception not in the allow-list indicate a driver bug, not a finding). If verification fails, update the exception allow-list or the entrypoint and rerun; do not silently accept the log.
- Finalize. Confirm the artifact set per library: `<lib>/fuzz.py`, `<lib>/fuzz.log`, `<lib>/.venv/`, plus repo-level `libraries.txt` and `notes_for_testing.txt`. Stop when every library in `libraries.txt` passes the verify step.

## Constraints / Pitfalls
- Do not catch `Exception` or `BaseException` broadly in `TestOneInput`; a bare `except` hides real crashes and defeats fuzzing. Only catch exceptions the library documents or raises for malformed input.
- Do not hard-code tool names: discover `uv`/`poetry`/`pip`/`python -m venv` presence before using them, and prefer the project's native tool when a lockfile is present.
- Do not reuse a single global venv across libraries; each library gets its own `.venv` to avoid dependency contamination.
- Do not use libFuzzer's `-runs=` flag when a time budget is required; use `-max_total_time=` so the run terminates deterministically and `fuzz.log` is complete.
- Do not pick an entrypoint that only runs trivial imports (for example importing a sub-namespace with no executable logic); the log must show `exec/s` progress and growing coverage counters.
- Do not treat a non-empty `fuzz.log` as success; it must contain the libFuzzer banner and progress lines and must not terminate on a driver-scaffolding traceback.
- Do not embed task-specific library names, versions, or paths into the driver template; derive them from discovery at runtime.
- If a dependency install or fuzz run fails twice with the same signal, escalate: switch entrypoint or narrow scope and document the change in `notes_for_testing.txt` rather than retrying identically.