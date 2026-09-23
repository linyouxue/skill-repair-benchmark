---
name: python-scala-api-compile-guardrails
version: 0.1.0
description: Guardrails to prevent Scala 2.13 compile/API-surface failures when translating a Python module into a single Scala file.
---

# Python → Scala: API-surface + Scala 2.13 compile guardrails

This skill adds **mechanical guardrails** on top of a translation playbook. It targets a common failure mode: producing a Scala file that *looks right* but **does not compile** or **misses required public symbols** (classes/functions), leading to a 0/1 outcome even when execution otherwise “seems OK”.

Use this when a task requires:

- translating one Python module into one Scala 2.13 file, and
- preserving a **named API surface** (a list of classes/functions that must exist).

## 1) Build an explicit “required symbol list”

Before writing Scala, copy the prompt’s required public names into a checklist.

Example (structure only):

- ADTs / enums: `TokenType`
- data classes: `Token`
- base traits/abstract classes: `BaseTokenizer`
- concrete classes: `StringTokenizer`, `NumericTokenizer`, ...
- builders/config: `TokenizerBuilder`
- functions/helpers: `tokenize`, `tokenizeBatch`, `toToken`, `withMetadata`

During implementation, keep this list visible and **strike items only when the Scala code contains the exact identifiers**.

## 2) Prefer a “single-file module layout” that compiles cleanly

A Scala 2.13 single file is easiest to keep correct with this layout:

```scala
// Imports

// === Public model (sealed traits, case classes) ===

// === Public tokenizer API types ===

// === Implementations (final classes) ===

// === Companion objects / top-level functions ===
```

Guardrail rules:

- Put all **public** types at top-level (not nested inside unrelated classes).
- Implement “top-level functions” as methods on a single `object` (Scala has no Python-style module functions).
- Avoid Scala 3 features: `enum`, `given`, `extension`, `using`, opaque types.
- Avoid placeholders (`???`) and unused abstract members.

## 3) Translation patterns that reduce compile errors

### 3.1 Optional fields and defaults

Python often omits fields or uses `None`. In Scala, prefer `Option` with defaults:

```scala
final case class Token(
  tokenType: TokenType,
  value: String,
  start: Option[Int] = None,
  end: Option[Int] = None,
  metadata: Map[String, String] = Map.empty
)
```

### 3.2 One place for helpers (avoid name drift)

If the prompt requires helper names (e.g., `withMetadata`, `toToken`), define them *once* in a stable location:

- `withMetadata`:
  - either as a `Token` method (preferred for readability), and/or
  - as a protected helper on `BaseTokenizer` if tokenizers must attach metadata.

- `toToken`:
  - implement as a function in an `object` so call sites are consistent.

### 3.3 Error handling

When translating parsing code:

- use `Try(x).toOption` for “best effort” parsing;
- use `Either[String, A]` when the caller needs to know failure reasons;
- avoid throwing unless Python code truly fails fast.

Keep the choice consistent across tokenizers.

## 4) Static “compile hygiene” scan (when `scalac` isn’t available)

When the environment doesn’t provide Scala tooling, do a manual scan that catches most failures:

- Every `{` has a matching `}` (watch nested objects/companions).
- No `???`, `null`, or unimplemented abstract methods.
- Every referenced type is imported or fully qualified.
- No use of Scala 3-only syntax.
- Public identifiers exactly match the required symbol list (case-sensitive).

## 5) Optional: add a lightweight symbol check step

If you can run *any* text search in the environment, verify identifiers exist in the produced file:

- search for `class StringTokenizer` / `trait BaseTokenizer` / `object TokenType` etc.

This doesn’t prove behavior, but it prevents “missing name” failures.

## 6) Done criteria

You are done when:

1. The required symbol list is fully satisfied in Scala, and
2. the file contains no placeholders, and
3. the code reads as idiomatic Scala 2.13 with `Option`/`Try`/`Either` used intentionally.
