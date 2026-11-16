# python-to-scala-module-translation

## Purpose
Translate a Python module into a single idiomatic Scala file whose public API preserves the Python call shape and error-handling contract, so a verifier that invokes the required symbols with native-typed inputs will succeed. Compilation is necessary but not sufficient; signature and behavioral parity are the primary targets.

## When to Use
Use when a task supplies a Python source (or module) and asks for a Scala translation at a specified output path, especially when it enumerates required classes/functions or requires "proper abstractions" and "natural error handling". Do not use for isolated snippet translation or Scala-only refactoring.

## Procedure
- Read the Python source end to end. Enumerate every public class, function, Protocol, TypeVar, Enum, dataclass, overload, and constant. Union with any task-specified names to form the required-symbols set.
- Build a signature table: for each required symbol, record the Python parameter types, return type, and raised exceptions. Translate each to a native-typed Scala expectation (e.g., `str` -> `String`, `bytes` -> `Array[Byte]`, `int` -> `Int`, `datetime` -> `LocalDateTime`, `list[T]` -> `Seq[T]`, `dict[K,V]` -> `Map[K,V]`). This table is the public-API contract for the Scala file.
- Discover the Scala toolchain (`build.sbt`, `build.sc`, `project/`, or `scalac` on PATH). Prefer the project's build tool; fall back to `scalac` only if no build file exists.
- Decide abstraction scope per symbol using this rule: if the symbol is in the required-symbols set (public surface), preserve its Python-shaped signature using native Scala types and overloads; if it is strictly internal, you may use sealed ADTs/Either freely. For public symbols, use ADT wrappers only when the task explicitly asks for typed inputs.
- Map constructs conditionally:
- `Enum` -> `sealed trait` + `case object`s (or Scala 3 `enum`).
- `@dataclass` / frozen -> `final case class` with `val` fields.
- `Protocol` with multiple concrete types -> `trait` with abstract members.
- `TypeVar('T', bound=X)` -> `[T <: X]`; variance only where the Python usage proves it.
- Union types on a public signature -> method overloads with native types, or a single method taking a sealed ADT only if the task explicitly requires it.
- `@overload` -> overloaded Scala methods matching each Python overload.
- Generators (`yield`) -> `LazyList` or `Iterator`.
- Map error handling conditionally: if the Python public symbol raises on bad input, mirror that behavior (throw `IllegalArgumentException`/`NoSuchElementException`/etc.) unless the task explicitly asks for `Option`/`Try`/`Either`. Use typed error channels for internal helpers where it clarifies control flow.
- Write the Scala file to the task-specified output path as one coherent unit: package, imports, ADTs, classes, then top-level functions.
- Signature-probe check: create a temporary probe `.scala` file that references each required symbol and calls it with native-typed literal arguments drawn from the signature table (e.g., `StringTokenizer().tokenize("abc")`). Compile the probe together with the output file. If any symbol is unreachable or signature-mismatched, record the diagnostic and apply the fallback below.
- Fallback (bounded, one retry): if the probe fails because a public symbol has an ADT-wrapped or Either-returning signature where the probe expects native types, add a native-typed overload or facade that forwards to the internal representation. Re-run the probe compile.
- Final compile: run the discovered toolchain on the output file (and keep the probe artifact out of the final deliverable). Fix diagnostics until exit 0.
- Clean up probe files and any scratch outputs before reporting completion.

## Constraints / Pitfalls
- Do not change the public call shape of any required symbol. Native Python types on the Python side map to native Scala types on the Scala side unless the task says otherwise.
- Do not convert raising public methods to `Either`/`Try` by default; mirror the Python exception contract. Convert only when the task explicitly requires typed error channels or the symbol is internal.
- Do not treat `scalac` exit 0 alone as success. The signature probe compile is the finalization gate.
- Do not use `Any`/`AnyRef` as a shortcut for a union; prefer overloads for public symbols and sealed ADTs only internally.
- Do not invent or rename required symbols. Preserve exact casing; convert `snake_case` to idiomatic Scala naming only when the task explicitly permits it.
- Do not hardcode toolchain commands; discover `sbt`/`mill`/`scalac` first and prefer the project's build.
- Keep output in one file at the exact task-specified path; do not split packages unless requested.
- Keep the fallback branch to a single retry; if the probe still fails, surface the signature mismatch instead of layering more wrappers.
- Annotate unbounded recursion with `@tailrec` and verify it compiles.