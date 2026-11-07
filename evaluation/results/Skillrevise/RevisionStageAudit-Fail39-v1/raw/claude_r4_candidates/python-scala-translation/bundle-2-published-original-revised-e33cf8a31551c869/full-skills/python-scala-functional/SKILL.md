# python-to-scala-module-translation

## Purpose
Translate a Python module into a single idiomatic Scala file whose symbol set, abstractions, and error handling satisfy a verifier that checks compilation, required-symbol presence, and Scala-idiomatic design.

## When to Use
Use when the task provides a Python source file (or module) and asks for a Scala translation at a specified output path, especially when the task enumerates required classes/functions or requires "proper abstractions" and "natural error handling". Do not use for isolated snippet translation or for Scala-only refactoring.

## Procedure
- Read the Python source end to end. List every class, function, Protocol, TypeVar, Enum, dataclass, overload, and public constant defined in it.
- Build a required-symbols set = union(task-specified names, public names from the source). Record it before writing code.
- Discover the Scala toolchain in the environment (check for `build.sbt`, `build.sc`, `project/`, or a direct `scalac` on PATH). Prefer the project's build tool; fall back to `scalac` only if no build file exists.
- Map each Python construct using this decision table:
- `Enum` -> `sealed trait` + `case object`s (or `enum` on Scala 3).
- `@dataclass` / `@dataclass(frozen=True)` -> `final case class` with `val` fields.
- `Protocol` / duck-typed interface -> `trait` with abstract members; use type class `given`/`implicit` only if dispatch is external.
- `TypeVar('T', bound=X)` -> `[T <: X]`; covariant containers -> `[+T]`; contravariant consumers -> `[-T]`. Never collapse a bounded or union type to `Any`.
- Union types (`str | bytes`, numeric unions) -> sealed ADT or `Either`; avoid `Any` with runtime `isInstanceOf`.
- `@overload` -> overloaded methods or a single method with pattern matching on a sealed ADT.
- Generators (`yield`) -> `LazyList` or `Iterator`.
- Mutable default args / kwargs -> immutable params, `Option`, or `Map[String, Any]` only when truly dynamic.
- Map error handling: if the Python function raises on user input (`ValueError`, `TypeError`, parse failures, missing keys), return `Option`, `Try`, or `Either[Err, A]`. Only throw for genuinely unreachable branches, and prefer `sys.error` / `IllegalStateException` with a comment.
- Write the Scala file to the specified output path in one coherent unit (package, imports, ADTs first, then classes, then top-level functions).
- Symbol-coverage check: for each name in the required-symbols set, grep the output file for its definition (`class`, `object`, `trait`, `def`, `val`). Add any missing symbol before compiling.
- Compile using the discovered toolchain. Fix diagnostics and recompile until exit 0.
- Remove any temporary files or scratch outputs created during translation.

## Constraints / Pitfalls
- Do not use `Any` or `AnyRef` as a stand-in for a union or bounded generic; if you reach for `Any`, stop and model a sealed ADT or `Either` instead.
- Do not throw exceptions in place of Python's user-input errors; use `Try`/`Either`/`Option`. Mixing thrown exceptions with "natural error handling" criteria typically fails verification.
- Do not invent symbols not in the source or task spec, and do not rename required symbols (preserve exact casing, converting `snake_case` only where the task explicitly allows idiomatic Scala naming).
- Do not hardcode toolchain commands; discover `sbt`/`mill`/`scalac` first.
- Keep the output in one file at the exact path the task specifies; do not split across packages unless requested.
- If recursion is unbounded over input size, annotate with `@tailrec` and verify it compiles.
- If evidence for a Python construct's intent is ambiguous, prefer the stricter Scala type (sealed ADT, bounded generic) over the permissive one.