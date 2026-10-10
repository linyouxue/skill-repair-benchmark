# Python Library Fuzz Driver Workflow (Atheris)

## Purpose
Produce a runnable Atheris fuzz driver for one or more Python libraries using a repeatable per-library workflow: discover the library, author a minimal driver, isolate its environment, execute a time-bounded validation run, and capture the log. The goal is a driver that exercises real library code without crashing on library-expected exceptions, not a crash-hunting campaign.

## When to Use
Use when the task asks you to create Atheris fuzz drivers / fuzz targets for one or more Python libraries and then run them for a bounded duration with log output. Do not use for native-extension sanitizer workflows, protobuf-structured fuzzing, or OSS-Fuzz integration unless the task explicitly requires them.

## Procedure
- Discover (per library)
- Locate the packaging file: `pyproject.toml`, `setup.py`, or `requirements.txt`. Record the import name (often differs from the distribution name).
- Identify a leaf utility module with a small, pure-Python entry point that accepts bytes/str/int (parsers, decoders, config/env readers, serializers, tokenizers, path/URL utilities). Prefer these over top-level API facades.
- Evidence: a chosen `module.function` whose signature can be driven from `FuzzedDataProvider`.
- Isolate environment (per library)
- Create a dedicated venv in the library directory: prefer `uv venv .venv` if `uv` is available, else `python -m venv .venv`. Activate it.
- Install Atheris: `pip install atheris` (or `uv pip install atheris`).
- Install the target library in editable mode from its packaging file. Prefer the full dependency set.
- Fallback: if install fails or pulls heavy stacks (GPU/ML/compilers) that exceed the environment, retry with `--no-deps` and pick a leaf module whose imports resolve under `--no-deps`. Verify by running `python -c "import <leaf_module>"` with exit 0.
- Author driver `fuzz.py` (per library)
- Start from this template; adapt the import and the single call site. Keep it minimal. ```python #!/usr/bin/env python3 import sys import atheris with atheris.instrument_imports(): from <package> import <leaf_module>  # adjust # Library-expected exceptions: extend only in response to a real run. EXPECTED = (ValueError, TypeError, UnicodeDecodeError, KeyError, OverflowError) @atheris.instrument_func def TestOneInput(data: bytes): fdp = atheris.FuzzedDataProvider(data) payload = fdp.ConsumeBytes(atheris.ALL_REMAINING) if hasattr(atheris, "ALL_REMAINING") else fdp.ConsumeBytes(len(data)) try: <leaf_module>.<entry>(payload)  # adjust: pass str/int/bytes as required except EXPECTED: return def main(): atheris.Setup(sys.argv, TestOneInput) atheris.Fuzz() if __name__ == "__main__": main() ```
- If the entry point requires `str`, use `fdp.ConsumeUnicodeNoSurrogates(n)`; for ints, `ConsumeIntInRange`.
- Evidence: `python -c "import fuzz"` under the venv exits 0.
- Bounded run and log (per library)
- `mkdir -p corpus`
- Run: `python fuzz.py -atheris_runs=0 -max_total_time=<N> corpus/ > fuzz.log 2>&1` where `<N>` is the task-specified duration (or a short default such as 10 if unspecified).
- Expected evidence in `fuzz.log`: libFuzzer banner (`INFO: Running with ...`), `INITED cov: ...`, periodic `exec/s:` or `NEW` lines, and clean termination near the time budget.
- The process should exit 0 at the time limit. A non-zero exit with `=== Uncaught Python exception: ===` indicates an unhandled library-expected exception.
- Verify and recover (per library)
- If step 4 produced an `Uncaught Python exception` whose type is a library-defined/expected error (not a true bug), add that exception type to the `EXPECTED` tuple and re-run step 4 once. Remove any crash-artifact file written to cwd.
- If `no interesting inputs were found` appears, confirm the import is inside `atheris.instrument_imports()` and that `@atheris.instrument_func` decorates `TestOneInput`.
- If coverage stays at `cov: 2`, the driver likely never reaches library code: re-check the entry call and input type.
- Stop when `fuzz.log` shows coverage growth (or steady exec/s on a trivial target) and clean timeout exit.

## Constraints / Pitfalls
- Do not call `exit()`, spawn unjoined threads, or introduce randomness not derived from `data` inside `TestOneInput`.
- `TestOneInput` must accept any `bytes` input (empty, huge, malformed) without raising uncaught exceptions.
- Catch only library-expected exceptions; never use a bare `except Exception` catch-all, which hides real bugs.
- No hard-coded library names, versions, or absolute paths. Everything is parameterized by the discovered package and chosen leaf module.
- Keep one driver per library in its own venv; do not share a global venv across targets with conflicting dependencies.
- Do not add protobuf mutators, custom crossover, coverage.py HTML, or native-extension sanitizers unless the task explicitly requires them.
- Prefer `-max_total_time` over `-runs`; `-runs` can prevent graceful exit and log flushing.
- When using `--no-deps` as a fallback, document the choice in any required notes file and pick a leaf module that imports cleanly under that constraint.