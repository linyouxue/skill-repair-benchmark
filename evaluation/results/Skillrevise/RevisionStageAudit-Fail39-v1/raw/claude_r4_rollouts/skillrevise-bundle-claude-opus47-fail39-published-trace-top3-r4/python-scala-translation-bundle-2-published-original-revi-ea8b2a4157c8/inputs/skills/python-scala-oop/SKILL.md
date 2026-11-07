# Python to Scala Translation Workflow

## Purpose
Translate a Python source file into a Scala source file that compiles under the project's actual Scala toolchain and preserves the symbols the task requires. The skill is a procedure for executing a translation, not a catalog of idioms.

## When to Use
Use when the task asks for translating a specific Python file (classes, functions, OOP constructs) to Scala and the result must compile and expose named symbols. Do not use for general Scala authoring, Scala-to-Python translation, or language advice unrelated to a concrete source file.

## Procedure
- Discover environment: run `scalac -version` (and inspect any build file such as `build.sbt`, `build.sc`, or project config) to determine the target Scala major version (2.12/2.13 vs 3.x). Record it; if `scalac` is missing, stop and report instead of guessing output.
- Discover inputs and contract: read the full Python source. Enumerate the required symbols (classes, methods, top-level functions, constants) and any list of required names the task specifies. Note which classes are subclassed, which are mutated, and which use `@dataclass`, `@property`, `@staticmethod`, `@classmethod`, `ABC`, or multiple inheritance.
- Plan abstractions with decision rules (apply per symbol, do not blanket-apply):
- If the Python class is subclassed anywhere in the file, map to a plain `class` or `abstract class`, not `case class` (case classes should not be extended by other case classes).
- If the class is a pure immutable value with structural equality and no subclasses, map to `case class`.
- If the Python construct is `ABC` with abstract methods, map to `trait` (or `abstract class` if constructor parameters are required under Scala 2).
- If multiple inheritance is used for mixins, map extra bases to `trait`s combined with `with`.
- If `@staticmethod` / `@classmethod` / module-level functions exist, place them in a companion `object` with the same name as the class or in a top-level `object` for module functions.
- If the Python code uses mutable attributes, model with `var` or an explicit setter; otherwise prefer `val`.
- Gate syntax by discovered Scala version:
- For Scala 2.x: forbid `enum ... case`, significant-indentation blocks, `given`/`using`, `extension` methods, and `export`. Use `sealed trait` + `case object` for enum-like types.
- For Scala 3.x: Scala 3 syntax is allowed but not required.
- Write the Scala file preserving every required symbol name exactly (class names, method names, constant names). Keep public API surface aligned with the Python original.
- Compile: run `scalac <output>.scala` (or the project's build command if one exists). On success, confirm `.class` files were produced and that `grep` for each required symbol name succeeds in the source. On failure, read the first error, apply the smallest fix consistent with the decision rules, and recompile. Cap at 5 recompile iterations.
- Recover on repeated failure: if compilation still fails after 5 attempts or the same error recurs, simplify the abstraction (drop variance annotations, replace inheritance from a case class with a plain class + companion, inline mixins) rather than adding more type machinery.
- Final verification: confirm (a) `scalac` exit code is 0, (b) every required symbol name appears in the output file, (c) no Scala-version-forbidden syntax is present. Only then report completion.

## Constraints / Pitfalls
- Do not apply "prefer case class" as a blanket rule; it breaks whenever the class must be extended or carries identity rather than value semantics.
- Do not emit Scala 3-only syntax when the discovered target is Scala 2.x, and vice versa; the version gate is mandatory.
- Do not rename symbols for stylistic reasons; the verifier may check exact names from the Python source.
- Do not silently drop methods or constants that lack an obvious Scala idiom; translate them literally first, then refactor only if compilation requires it.
- Do not invent output paths; write to the path specified by the task. If none is specified, place the file next to the Python source with a `.scala` extension and report the path.
- Do not finish without a successful `scalac` run; a syntactically plausible file is not acceptance evidence.