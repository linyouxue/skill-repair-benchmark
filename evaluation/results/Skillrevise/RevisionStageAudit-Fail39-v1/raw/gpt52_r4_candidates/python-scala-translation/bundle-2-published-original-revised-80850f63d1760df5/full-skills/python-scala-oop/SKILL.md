# Python Module to Scala 2.13 API-Complete Translation (OOP and Tokenizers)

## Purpose
Translate a Python module that defines multiple classes and functions into Scala 2.13 while preserving the module's public API (required symbol names) and core semantics, with completion gated by symbol checks and a real Scala compilation.

## When to Use
Use when the task requires a full-file Python-to-Scala translation with an explicit list of required classes/functions (exact names) and a requirement to compile under Scala 2.13. Do not use for partial refactors, style-only rewrites, or when no symbol-level contract is given.

## Procedure
- Step 1: Read and validate inputs before writing code.
- Locate and open the full Python source file(s) to be translated.
- Extract two lists:
- Source Inventory: every top-level class, function, and constant actually defined in the Python module (names plus signatures).
- Required Symbols: every class/function/object name explicitly required by the task instructions.
- Decision: If Required Symbols contains names not present in the Python file, stop and request clarification (do not invent new APIs).
- Step 2: Establish translation mapping from observed constructs (discovery-driven).
- For each Python definition in the Source Inventory, note only behavior-critical details:
- Constructor parameters and defaults, required fields, mutability, and runtime checks.
- Exceptions raised vs silent behavior, None handling, and type conversions.
- Any classmethod/staticmethod usage, module-level helper functions, and global configuration constants.
- Choose Scala representations based on what is present:
- dataclass-like immutable record -> case class (only if immutability matches behavior).
- ABC/abstract base -> trait/abstract class with abstract defs.
- Python properties with validation -> explicit getter/setter methods (or keep vars) only if setters exist and behavior requires mutation.
- Step 3: Implement translation one symbol at a time (minimize drift).
- Create the Scala file(s) at the task-specified location; if no location is specified, discover the repository conventions (existing src directories, build files) and place code where Scala build tools will compile it.
- Implement each required symbol from Required Symbols first, then any additional symbols from Source Inventory needed as dependencies.
- After implementing a symbol, add a small internal comment listing the Python source name and any semantic choices (only where ambiguity exists).
- Decision: If a Python behavior is ambiguous (e.g., dynamic typing or duck-typed inputs), prefer the least-committal Scala signature that still compiles and matches behavior (e.g., String vs Any) and document the assumption locally; do not introduce new frameworks or abstractions to "improve" design.
- Step 4: Post-write validation gate (must pass before claiming completion).
- Schema-like symbol check:
- Mechanically verify the Scala output contains every name in Required Symbols as a top-level definition (class/trait/object/def) and that names match exactly (case-sensitive).
- If a required symbol is missing or nested incorrectly, fix structure before further edits.
- Compilation check:
- Discover the available toolchain: try scalac first; if absent, look for sbt or mill; use what exists.
- Run a Scala 2.13 compilation (scalac compile or sbt compile) and iterate on errors until clean.
- Optional parity spot-check (only if runnable in the environment):
- Run a minimal sanity check that exercises the key entrypoints (for tokenizers: tokenize/tokenizeBatch and basic class construction) without adding new dependencies.

## Constraints / Pitfalls
- Do not invent extra subsystems, helper frameworks, registries, monads/functors, JSON layers, or new public APIs unless they exist in the Python source file or are explicitly required by the task contract.
- Do not mark the task complete without (1) a required-symbol checklist showing all required names present and (2) a successful Scala 2.13 compilation in the actual environment; if tools are missing, stop and report what is available and what cannot be verified.