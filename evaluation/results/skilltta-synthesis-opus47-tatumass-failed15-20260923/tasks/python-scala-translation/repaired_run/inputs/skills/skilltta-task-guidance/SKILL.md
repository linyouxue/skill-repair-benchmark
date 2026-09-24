---
name: skilltta-task-guidance
description: Task-specific operational guidance synthesized at test time from retrieved training examples.
---

# SKILL.md

## When to use
Use this skill when the target task asks you to translate a Python module into idiomatic Scala (here, Scala 2.13) preserving a specified public API — a list of classes/objects, functions, and methods that must exist by name. The binding contract requires that:
- Every named entity from the Python source is present in the Scala output at the specified path.
- The Scala code compiles under the required Scala version.
- Behavior matches the Python source semantically (not textually).
- The output follows Scala idioms and naming conventions rather than being a line-for-line port.

Before acting, gather:
- The full contents of the Python source file (read it end-to-end; do not guess based on class names).
- Every top-level and nested symbol name required by the prompt, and note which are classes vs. functions vs. methods.
- The Python semantics for error handling, optionality, mutability, and any regex/date/number parsing.
- The exact output file path and Scala version constraint.

## Possible Failure Modes
- Missing a required symbol from the mandated list (e.g., forgetting a helper like `toToken`, `withMetadata`, or a builder), or defining it with the wrong arity/case so callers can't find it.
- Word-for-word translation: using `null`, mutable `var`s, uppercase `SCREAMING_SNAKE` constants, Python-style `class` hierarchies with mutable fields, or Java-style getters instead of idiomatic Scala.
- Wrong naming conventions: methods should be `camelCase`, types `PascalCase`, packages lowercase; enum-like values as `case object`s inside a `sealed trait`.
- Using exceptions where `Option`, `Either`, or `Try` is more idiomatic — or the reverse: silently swallowing errors the Python code raises.
- Ignoring Scala 2.13 specifics: using Scala 3 syntax (`enum`, `given`, indentation-based blocks, `extension`), or using deprecated 2.12 collection APIs.
- Reinventing utilities that exist in the standard library (`scala.util.Try`, `scala.util.matching.Regex`, `java.time.*`, `String.split`, `mkString`, `groupBy`, `foldLeft`).
- Breaking builder/fluent APIs by returning `Unit` instead of `this` (or a new immutable copy).
- Losing type information via `Any` when a `sealed trait` ADT is the right model (e.g., a `TokenType` should be a sealed ADT).
- Not producing a self-contained, compilable file: missing imports, dangling references, or package declarations inconsistent with the required path.
- Copying identifier names, structure, or specifics from unrelated retrieved examples that have nothing to do with the actual Python source.

## Possible procedures
1. Read the Python source completely and enumerate:
   - Required classes/objects/traits and their public methods.
   - Constructor parameters and default values.
   - Any module-level constants, enums, and regex patterns.
   - Exception types raised and where `None`/optional values flow.
2. Map Python constructs to idiomatic Scala:
   - Python enum / string-typed kinds → `sealed trait` + `case object`s (often in a companion `object`).
   - Dataclass-like containers → `final case class` with immutable `val` fields; provide `copy`-based updates (e.g., `withMetadata` returns a new instance).
   - Abstract base class with subclasses → `sealed abstract class` or `trait` with concrete subclasses; use `abstract def` for polymorphic methods.
   - Builder pattern → immutable builder that returns a new builder from each setter, plus a terminal `build`.
   - `Optional`/`None` → `Option[T]`; raising exceptions on invalid input → `Either[Error, T]` or `Try[T]`, unless the contract clearly wants exceptions.
   - Regex → `scala.util.matching.Regex`; date/time → `java.time` (LocalDate/Instant/DateTimeFormatter).
   - Batch/loop tokenization → prefer collection combinators (`map`, `flatMap`, `collect`) over mutable buffers; if performance matters, `Vector`/`ArrayBuffer` locally is fine.
3. Preserve the exact required symbol names. If Python uses `snake_case` for methods, still expose those names if the contract lists them literally; otherwise convert to `camelCase`. When in doubt, keep the names from the required list verbatim so grading can find them.
4. Structure the file:
   - Single package/object or a top-level `object` wrapping helpers is fine; ensure top-level `def`s that the contract names (like `tokenize`, `tokenizeBatch`) are reachable (e.g., via an `object` with the module name or as methods on a stated class).
   - Companion objects for `apply`, factory methods, and constants.
5. Compilation check mentally: for every call site, verify types line up; avoid implicit conversions that don't exist in 2.13; don't use `enum` (Scala 3 only).
6. Handle errors naturally: validate inputs at construction (e.g., `require(...)`), return `Option`/`Either` for parse-like operations, and reserve exceptions for truly exceptional cases.
7. If any Python behavior is ambiguous (e.g., unicode handling, empty input), choose the closest Scala-idiomatic behavior and document it briefly in a Scaladoc comment.

## Verification Checklist
- [ ] Output file is written to the exact path specified in the prompt.
- [ ] Every symbol named in the prompt exists in the Scala source with a matching role (class/object/trait vs. function/method) and reachable from a top-level scope.
- [ ] File declares/uses only Scala 2.13-compatible syntax (no `enum`, no `given/using`, no Scala 3 braceless syntax where it would fail).
- [ ] All imports are present; the file would compile standalone (`scalac Tokenizer.scala` mentally passes).
- [ ] Types are precise: no gratuitous `Any`; ADTs used for enum-like values; `Option`/`Either`/`Try` used for absence/failure instead of `null`.
- [ ] Naming follows Scala conventions (`PascalCase` types, `camelCase` methods/vals) while still exposing every name the prompt requires.
- [ ] No mutable global state; case classes are immutable; builder methods return new instances.
- [ ] Standard library used for regex, time, and collections rather than hand-rolled equivalents.
- [ ] Behavior matches the Python source on representative inputs (empty input, whitespace, numeric edge cases, temporal parse failures).
- [ ] No identifiers, comments, or logic copied from unrelated retrieved examples; content is derived only from the actual Python source.
- [ ] Unrelated files under `/root/` are not modified or deleted.
- [ ] Recovery: if the Python source references something unclear, re-read it before guessing; if a required name is genuinely absent from Python, still create a sensible Scala counterpart so the required list is satisfied.
