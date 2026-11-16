# Python-to-Scala 2.13 Module Translation With Verifier-Aligned API Parity

## Purpose
Translate an entire Python module into Scala 2.13 while preserving the verifier-visible public API (names, signatures, and symbol placement), using a checkpointed workflow that discovers requirements, implements incrementally, and validates outputs (paths, compilation, and API surface) before claiming completion.

## When to Use
Use when a task requires converting a Python file/module to Scala (or Scala-like JVM language) under strict verification that depends on exact symbol names/signatures (classes, traits, objects, functions, and required methods). Do not use for "make it idiomatic" rewrites where API compatibility is not required.

## Procedure
- 1) Discover the contract (inputs, outputs, and toolchain)
- Read the task instructions and locate the Python source(s) to translate.
- Extract: required Scala version (for example, 2.13), required symbol list (if provided), and required output path(s).
- If output path(s) are not explicitly given, discover the expected location by inspecting repository structure (for example, existing src layout, build files) and do not guess; if still ambiguous, stop and ask for clarification.
- Check tool availability in the environment (for example, scalac/scala/sbt). If missing, switch to producing source only and add a clear note that compilation could not be executed here.
- 2) Build an API inventory from the Python code (schema for translation)
- Enumerate all top-level definitions: classes, functions, constants, and any required entrypoints.
- For each class: list constructor parameters, public methods/properties, and any inheritance/Protocol-like requirements.
- Record naming constraints: whether the verifier expects snake_case names to remain (or expects a camelCase mapping). Do not rename unless the task explicitly requires the mapping; if unsure, preserve original names and add thin aliases only when verified safe.
- 3) Decide Scala surface and placement before coding
- Choose where each symbol will live (top-level definitions vs inside an object/package) based on the task/repo conventions discovered in step 1.
- Define a mapping table for Python types/features encountered (only as needed):
- Optional/None: Option[T]
- Union: Either-like encoding or sealed trait ADT (choose the simplest that preserves call sites)
- Exceptions: Try[T] or Either[Error, T] depending on call semantics
- Generators: Iterator[T] or LazyList[T]
- Python duck typing/Protocol: trait + concrete implementations; avoid advanced features unless required
- Create a checklist of required public symbols (from task + Python inventory). This checklist is the output schema you will validate later.
- 4) Implement incrementally with safety checkpoints
- Implement skeletons first: declare all required classes/traits/objects/defs with correct names and minimal compilable signatures.
- Fill in behavior next, prioritizing correctness over idiomatic refactors that change observable behavior.
- After each cluster of related symbols, run a compile check with the discovered tool (scalac or sbt) and fix errors immediately; do not continue accumulating errors.
- 5) Verify against the observable contract (do not skip)
- Output-path grounding check:
- Assert the Scala file(s) exist and are readable at the exact task-required path(s).
- If the write location differs from what the task requires, move/adjust only after confirming permissions/mounts; do not silently choose a different directory.
- Compilation check:
- Compile using the discovered Scala 2.13 toolchain and record the exact command/output used.
- If compilation cannot be run, explicitly mark this and do not claim verifier readiness.
- API schema check (post-write validation):
- Re-scan the produced Scala sources and confirm every required symbol name from the checklist appears (class/trait/object/def).
- If the verifier likely uses reflection/name lookup, add a small, local harness (only if runnable) that attempts to reference or reflectively load the symbols; fail fast if any are missing.
- If any required symbol is missing/renamed/misplaced, return to step 3 (placement) or step 4 (implementation) and repair; do not declare completion.

## Constraints / Pitfalls
- Do not refactor in ways that change the public API surface (rename, re-home into a different object/package, change parameter lists/return types) unless the task explicitly allows it and you re-run the API schema check afterward.
- Do not hard-code output paths, package names, build commands, or Scala versions unless they are explicitly required or discovered in the environment; always verify tool availability and file placement before and after writing.