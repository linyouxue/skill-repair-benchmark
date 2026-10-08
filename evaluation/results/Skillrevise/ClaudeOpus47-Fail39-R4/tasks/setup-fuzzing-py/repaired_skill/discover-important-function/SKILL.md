# Fuzz Pipeline Setup For Python Libraries

## Purpose
Given one or more Python libraries, produce the full artifact set a fuzzing pipeline needs: a libraries listing, per-library target notes, Atheris LibFuzzer harnesses, an isolated virtual environment with installed dependencies, a bounded fuzz run, and a captured log. Target selection is one phase inside this pipeline, not the whole skill.

## When to Use
Use when the task asks you to set up or extend a fuzzing workflow for Python packages, including choosing fuzz targets, writing harnesses, installing dependencies, running Atheris for a bounded time, and emitting named output artifacts at task-specified paths.

## Procedure
- Parse the task contract first. Extract from the instruction: (a) the list of target libraries, (b) each required output artifact name and path (for example a libraries listing, a notes file, one or more harness scripts, a fuzz log), (c) the required fuzz runtime budget, and (d) any venv or tool conventions. Do not assume filenames like `APIs.txt`; use only paths the task supplies. If a path is unspecified, discover a sensible location by inspecting the repo root and record the choice in the notes artifact.
- Discover the environment. Check availability of `python3`, `pip`, `venv`/`virtualenv`, `atheris`, and a directory lister (`tree` if present, else `find . -maxdepth N -type f`). Record which tools exist; use the first available option in each category rather than a fixed command.
- Create and populate the virtual environment at the task-specified location (default `.venv` if unspecified). Install `atheris` plus each target library. If `pip install <lib>` fails due to heavy or unresolved dependencies: (a) retry with `--no-deps`, (b) install only the minimal submodule dependencies needed by the chosen fuzz target, (c) if still blocked, pick a different FUT whose import graph avoids the missing dependency. Record every fallback in the notes artifact.
- Localize fuzz-worthy code per library. For each library, build a short ranked shortlist (1-5 FUTs) using boundary-code heuristics: parsers, decoders, deserializers, validators, format handlers (json/yaml/xml/toml/pickle/protobuf), regex-heavy code, native bindings, and public API re-exports. Use AST header+docstring scanning first; read full bodies only for finalists. Cross-reference existing tests to down-rank well-covered functions unless they are high-risk boundaries, and to extract seed inputs and oracles.
- Write the notes artifact. For each selected FUT include only: qualname, file:line, import path reachable in the venv, input type, invalid-input exceptions to treat as early-exit, suspicious exceptions to treat as real crashes, oracle (crash-only or property), and seed sources. Keep each note compact.
- Write one Atheris harness per selected FUT at the task-specified path. Harness shape:
- `import atheris` and `with atheris.instrument_imports(): import <target_module>`
- Define `INVALID_INPUT_EXCEPTIONS = (<documented invalid-input exceptions>)`
- `def TestOneInput(data):` build the typed input via `atheris.FuzzedDataProvider` or direct `bytes`/`str` decoding, call the FUT inside `try/except INVALID_INPUT_EXCEPTIONS: return`, let other exceptions propagate.
- `atheris.Setup(sys.argv, TestOneInput); atheris.Fuzz()` Verify each harness imports cleanly inside the venv before running.
- Run each harness for the task-specified bounded duration (default 10 seconds if unspecified) using Atheris's `-max_total_time=<N>` or an external timeout, and redirect combined stdout+stderr to the task-specified log path (for example `fuzz.log`). Do not run unbounded.
- Final verification anchor. For every required artifact path, confirm the file exists and is non-empty; confirm the log contains the Atheris banner and at least one iteration count line; confirm no crash in the log corresponds to a documented invalid-input exception. If any check fails, repair the responsible step (not the artifact in isolation) before declaring completion.

## Constraints / Pitfalls
- Never hard-code output filenames; always read them from the task instruction and fall back to discovery only when the task is silent.
- Keep the FUT shortlist to 1-5 per library; prefer targets reachable without heavy optional dependencies.
- Distinguish invalid-input exceptions (caught, early-return) from real crashes (propagate). Enumerate the invalid set in both the notes and the harness, and keep them in sync.
- All installs and runs must occur inside the isolated venv; do not pollute the system interpreter.
- Fuzz runs must be time-bounded and log-redirected; do not stream unbounded output.
- Do not modify library source code; analysis and harness code only.
- Keep the notes artifact short and action-oriented; omit template fields that have no evidence rather than filling them with speculation.
- If a tool literal (`tree`, specific pip flag) is unavailable, substitute the closest supported alternative discovered in step 2 instead of failing.