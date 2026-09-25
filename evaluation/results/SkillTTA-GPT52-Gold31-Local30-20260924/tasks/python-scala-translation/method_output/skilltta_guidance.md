# SKILL.md

## When to use
Use this skill when you must translate an existing Python module into **Scala 2.13** for distributed/big-data usage, while **preserving behavior** and exposing the **same public API surface** (same set of classes/functions) but expressed in **idiomatic Scala**.

Before implementing, gather evidence by:
- Reading the Python source end-to-end to identify:
  - Public entities (enums/constants, classes, methods, top-level functions) and their signatures/semantics.
  - Tokenization rules (regexes, parsing logic, edge cases, normalization steps).
  - Data structures returned (e.g., token objects, metadata fields, lists vs iterables, ordering guarantees).
  - Error/exception behavior and how “missing/invalid” inputs are handled.
- Noting dependencies (stdlib-only vs third-party), performance assumptions, and any implicit global state.

## Possible Failure Modes
- **API mismatch:** Missing any required class/function, wrong visibility, wrong method names/casing, or different parameter/return types that break compilation or evaluator reflection.
- **Behavioral drift:** A “literal” translation that subtly changes semantics (regex differences, Unicode/whitespace handling, numeric parsing differences, date/time parsing differences, token boundary rules).
- **Incorrect error handling:** Throwing exceptions where Python returned empty results (or vice versa); failing to represent absence naturally (using `null` instead of `Option`).
- **Metadata loss or mutation:** Dropping token metadata fields, changing defaults, or mutating shared metadata maps across tokens.
- **Batch processing pitfalls:** Implementing batch tokenization with eager materialization that is memory-heavy; losing per-record association; inconsistent ordering.
- **Scala antipatterns:** Overusing inheritance, mutable state, `var`, or Java-style code; poor separation of concerns (parsing vs representation).
- **Non-compiling Scala 2.13:** Using Scala 3 syntax/APIs, missing imports, or relying on unavailable libraries.
- **Locale/timezone surprises:** Using locale-dependent parsing/formatting or system-default timezone when Python behavior is deterministic.

## Possible procedures
1. **Inventory & contract extraction**
   - List all required entities (types/classes/functions) and confirm each one exists in Python.
   - For each entity, document:
     - Inputs/outputs, invariants (e.g., token text non-empty?), and side effects.
     - Error/edge-case behavior (empty strings, null-like values, invalid formats).

2. **Design Scala data model (idiomatic but compatible)**
   - Represent token categories using `sealed trait` + `case object`s (or an `Enumeration` only if truly necessary).
   - Represent tokens as `final case class` with clear fields (value, type, offsets, metadata, etc. as inferred).
   - Prefer immutable collections (`List`, `Vector`, `Map`) and avoid shared mutable state.

3. **Map Python parsing/tokenizing logic to Scala primitives**
   - Use Scala/Java standard libraries:
     - Regex: `scala.util.matching.Regex` or `java.util.regex.Pattern` for performance.
     - Numeric parsing: `BigDecimal`, `Try`, and explicit trimming/normalization.
     - Date/time: `java.time` (`LocalDate`, `Instant`, `DateTimeFormatter`) with explicit formatters; isolate parsing attempts.
   - Keep tokenization rules centralized to avoid divergence between single-item and batch paths.

4. **Implement tokenizers with clear abstraction boundaries**
   - Define a common tokenizer interface/abstract class mirroring the Python structure (e.g., base tokenizer + specialized ones).
   - Encapsulate each token type’s recognition/parsing in its own component:
     - `StringTokenizer`, `NumericTokenizer`, `TemporalTokenizer`, `WhitespaceTokenizer`, etc.
   - If the Python code uses composition/selection (e.g., “universal” tokenizer that tries multiple strategies), implement that explicitly:
     - Decision point: deterministic priority order of strategies must match Python.

5. **Handle absence and errors in Scala-native ways**
   - Use `Option` for absence and `Either`/`Try` for recoverable parse failures.
   - Convert to exceptions only at the API boundary if Python raised (or if the contract requires hard failure).
   - Avoid `null`; if interop requires it, confine it to a tiny boundary.

6. **Batch APIs for distributed settings**
   - Implement `tokenizeBatch` to work efficiently with iterables/iterators:
     - Prefer streaming (`Iterator`) internally; allow caller to choose materialization.
   - Ensure per-input output ordering and stable token ordering within each input.

7. **Builder pattern and configuration**
   - If a builder exists in Python, create an immutable Scala builder:
     - Use `case class` configuration + fluent `withX(...)` methods that return updated copies.
   - Ensure defaults match Python defaults.

8. **Recovery checks during implementation**
   - After implementing each tokenizer, create minimal internal sanity checks:
     - Representative inputs (empty, whitespace-only, mixed types, invalid numbers/dates).
   - Verify that the “universal” tokenizer delegates correctly and that `toToken`/`withMetadata` behave consistently.

## Verification Checklist
- **API completeness**
  - All required classes/functions are present with correct names: token type representation, token data type, tokenizer base/specializations, builder, and top-level helpers.
- **Scala 2.13 compilation**
  - `scalac` succeeds with Scala 2.13 syntax and only standard-library/Java-time dependencies unless the task context explicitly permits others.
- **Behavior parity**
  - Token boundaries, token types, ordering, normalization, and metadata behavior match the Python implementation for:
    - Empty input, whitespace-only input, mixed alphanumeric input, punctuation-heavy input.
    - Invalid numeric/temporal inputs (confirm whether they produce fallback tokens, omitted tokens, or errors).
- **Error/absence handling**
  - No `null` leaks; `Option`/`Either`/`Try` used consistently; externally visible error behavior matches Python expectations.
- **No accidental mutation**
  - Metadata/maps are not shared mutably across tokens; builder/config changes don’t mutate existing instances.
- **Batch correctness & efficiency**
  - `tokenizeBatch` preserves input-to-output alignment and does not unnecessarily load entire datasets when an iterator-based approach suffices.
- **Conventions & maintainability**
  - Scala naming conventions followed; code organized (files/classes), readable, and modular (each tokenizer focused).
- **Non-copying constraint**
  - Do not import assumptions from retrieved examples (paths, constants, specific token rules); only rely on the Python source and target task context.
- **Ambiguity recovery**
  - If any Python behavior is unclear (implicit defaults, exception types), add targeted tests/logical probes locally and re-check the Python code path before finalizing Scala behavior.
