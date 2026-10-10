# Python Library Fuzz Driver Workflow (Atheris)

## Purpose
Produce, per target library, an Atheris fuzz driver that reaches non-trivial pure-Python code in that library, runs for a bounded duration, exits cleanly, and leaves a log showing coverage growth into the library itself. Depth of reach, not crash hunting, is the success criterion.

## When to Use
Use when the task asks for Atheris fuzz drivers against one or more Python libraries with a bounded run and log output. Do not use for native-sanitizer, protobuf-structured, or OSS-Fuzz workflows unless explicitly required.

## Procedure
- Discover. For each library, read its packaging file and record the import name. Pick a leaf module that (a) lives inside the target package's installed source, (b) is pure Python with branching logic (parsers, decoders, tokenizers, path/URL/config utilities), and (c) exposes a function accepting bytes/str/int. Reject trivial helpers (small arithmetic/wrapper modules) and C extensions as the sole target.
- Isolate. Create a per-library venv. Install atheris and the target library from its packaging file. If install pulls heavy optional deps, retry with --no-deps; if the package __init__ then fails to import due to optional submodules, prefer a sub-package with a lightweight __init__ or temporarily stub the offending optional import, rather than bypassing import to reach a trivial helper.
- Author driver. Write fuzz.py that calls atheris.instrument_imports() around the target import, uses FuzzedDataProvider to shape input to the entry's required type, and calls the entry exactly once per TestOneInput. Start the expected-exception tuple empty; add a type only after observing it in a real run log AND confirming its traceback frame is inside the target package. Cap additions at five. Never use bare except.
- Bounded run. Create corpus/ and run `python fuzz.py -atheris_runs=0 -max_total_time=<N> corpus/ > fuzz.log 2>&1` with N from the task (short default if unspecified).
- Verify depth. In fuzz.log, confirm the libFuzzer banner, an INITED cov line, and a final cov value greater than INITED. Then run `python -c "import <leaf>; print(<leaf>.__file__)"` and confirm the path is inside the installed target package and ends in .py. If either check fails, go to Recover.
- Recover depth. If leaf is a C extension (.so/.pyd) or cov never grew past INITED, reselect a pure-Python branching module inside the same package (or wrap the C call with a Python-level parsing/validation path exercising branches) and re-run once. If an uncaught exception banner appears whose traceback originates inside the target package and is documented as library-raised, add that type to the expected tuple and re-run once.

## Constraints / Pitfalls
- Steady exec/s is not success; coverage must grow into target-library Python code.
- Do not accept a trivial helper or an uninstrumented C extension as the sole fuzz target.
- No hard-coded library names, versions, paths, or exception lists; discover and justify each addition from log evidence.
- Do not call exit(), spawn threads, or introduce non-input randomness in TestOneInput.
- One driver per library, one venv per library; never share venvs across targets with conflicting deps.
- Prefer -max_total_time over -runs so the process exits cleanly and flushes the log.
- Do not add protobuf mutators, custom crossover, coverage HTML, or native sanitizers unless the task requires them.