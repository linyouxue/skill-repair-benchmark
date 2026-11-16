# fuzzing-python-atheris-drivers

## Purpose
Create and validate reusable Atheris (LibFuzzer-style) fuzz drivers for Python libraries in a way that is repeatable across different repositories, environments, and packaging layouts, producing verifiable evidence that the fuzzer actually ran.

## When to Use
Use when you must add one or more Python fuzz targets (fuzz drivers) to existing Python repositories and prove they run (for a bounded time or bounded runs) under an isolated environment, while handling unknown packaging/dependency setups and avoiding brittle assumptions.

## Procedure
- Checkpoint 0: Clarify the task contract (before editing files)
- Identify required artifacts and locations from the task/verifier instructions (if any). If unspecified, decide and record a consistent convention per repo (for example: a fuzz script at repo root, a corpus directory, and a run log).
- Decision: single-repo vs multi-repo.
- If multi-repo, discover repo roots by listing the provided workspace directory and selecting directories that look like Python projects (pyproject.toml, setup.py, requirements*.txt).
- Evidence: a written plan listing each repo root, the intended fuzz driver filename(s), and how you will run a bounded smoke test.
- Checkpoint 1: Discover the target API surface to fuzz (per repo)
- Inspect the library package name and entrypoints without guessing:
- Look for pyproject.toml/setup.cfg/setup.py to learn the import name(s).
- Search for parsing/decoding/formatting/loading entrypoints that accept bytes or strings and are deterministic.
- Pick a narrow target function/method that:
- Can be called repeatedly in-process.
- Can reject malformed input quickly.
- Does not require network access or external services.
- Evidence: a short note (in your working notes or repo notes file) naming the chosen import path and callable, plus any required minimal initialization.
- Checkpoint 2: Create an isolated Python environment and install dependencies (per repo)
- Validate tool availability first:
- Confirm python3 is available and record its version.
- Detect whether a project tool is required/available (for example, uv/poetry/pip). Prefer using the repo-declared method if present and workable.
- Preferred install path (choose the first that matches the repo and succeeds):
- If a lockfile/tooling is present and installed (for example, uv.lock with uv available, or poetry.lock with poetry available), use that tool to create/sync an environment in a repo-local location.
- Otherwise, create a venv with python -m venv and install:
- Upgrade pip/setuptools/wheel if needed.
- Install the project (editable if appropriate) and its declared dependencies.
- Install atheris into the same environment.
- Bounded fallback if install fails:
- Inspect the error (missing compiler headers, failing native extension, incompatible dependency).
- Try the closest alternative install method (tool to pip/venv or vice versa) exactly once.
- If still failing, narrow scope: choose a target module/subpackage that imports with fewer extras, or install the project with reduced extras, and explicitly record the limitation in the repo notes. Do not silently skip dependencies.
- Evidence: within the environment, an import check succeeds for (a) atheris and (b) the chosen target module (run a minimal python -c import test).
- Checkpoint 3: Author the fuzz driver (per repo)
- Create a single executable fuzz script that:
- Imports atheris first.
- Instruments imports (use with atheris.instrument_imports():) around importing the target module(s).
- Defines TestOneInput(data: bytes) and calls the chosen target callable.
- Uses atheris.Setup(sys.argv, TestOneInput) then atheris.Fuzz().
- Exception policy (strict, to avoid hiding real bugs):
- Default: do not catch exceptions; let uncaught exceptions crash the fuzzer.
- Only catch-and-return for exceptions that are clearly part of input validation for malformed inputs (for example, documented parse errors), and keep the catch list minimal and explicit.
- Never blanket-catch Exception.
- If too many "expected" exceptions occur, do not expand the catch list immediately; instead narrow the target call or use FuzzedDataProvider to shape inputs (for example, bounded sizes, valid encodings) and retry.
- Evidence: the fuzz script is syntactically valid and can be imported/executed up to (but not including) Fuzz() setup without error.
- Checkpoint 4: Verify the driver runs and produces run evidence (per repo) (EXECUTION ANCHOR)
- Run a bounded smoke test inside the repo environment, capturing output to a log:
- Prefer a wall-clock bound if supported by the underlying engine in your environment; otherwise use an Atheris run-count bound.
- Use a corpus directory (create an empty one if needed) and pass it as an argument if the runner expects it.
- Validate the run did real work:
- The process should not exit immediately due to ImportError/ModuleNotFoundError.
- The log should contain an Atheris/LibFuzzer startup banner and at least one progress indicator (for example, INITED/pulse/NEW or equivalent) OR clear evidence that TestOneInput was invoked.
- If it exits due to an exception, confirm the exception is either:
- A real crash worth reporting (keep as failure), or
- An explicitly allowed "invalid input" exception per your documented exception policy (adjust the driver narrowly, then rerun the smallest bound again).
- Bounded fallback if the run fails:
- If "no interesting inputs were found" appears, instrument TestOneInput (decorator) or instrument all, then rerun the same bound.
- If it is too slow or hangs, add strict input size bounds and remove expensive code paths; rerun.
- Evidence: a log file exists, is non-empty, and indicates successful bounded execution (time/runs reached) or a reproducible crash with a stack trace.

## Constraints / Pitfalls
- Do not hard-code repo paths, package names, dependency managers, or run flags without first discovering them in the environment; always verify via an import check and a bounded smoke run.
- Do not suppress failures by catching broad exceptions; only catch narrowly justified "invalid input" errors, document why they are expected, and prefer narrowing the target or shaping inputs over expanding exception filters.