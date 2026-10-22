# Scala Module Translation With Verifier-Visible API Parity

## Purpose
Provide a repeatable workflow for translating a Python module into Scala while preserving the module's public API surface (names, scopes, and callable entrypoints) in a verifier-sensitive environment. The procedure emphasizes environment discovery, symbol inventory, scope/signature checkpoints, and post-write validation beyond compilation.

## When to Use
Use this when a task requires converting an existing Python module into Scala and the evaluator/verifier likely reflects or calls specific classes/functions by exact name (including top-level functions) and expects behavior parity, not just successful compilation.

## Procedure
- Step 1: Discover environment and constraints before coding
- Locate the Scala build entrypoint by inspection (examples: build.sbt, project/, build.sc, scala-cli directives, README).
- Determine Scala version and allowed dependencies from the build files; if unclear, run the build tool help/version command that is available in the environment.
- Decision point: If a third-party library is not already declared, do not introduce it; plan an implementation using only Scala/Java standard library features.
- Step 2: Extract and freeze the required public API contract
- Read the Python source and the task instructions to build a required-symbol list:
- Types: classes, dataclasses, enums, constants.
- Callables: module-level functions, class methods, factory/builders.
- Required names and casing must be captured exactly.
- Record intended Scala placement for each symbol (package, object/companion object, class/trait).
- Decision point: If the task mentions specific symbols explicitly, treat that list as non-negotiable even if the Python code seems to allow simplification.
- Step 3: Create a Scala skeleton that matches the API surface exactly
- Create package/object structure first, then stub every required symbol with correct visibility and an implementation placeholder.
- Ensure module-level Python functions become Scala methods in a stable, discoverable location consistent with the repository conventions (commonly an object that mirrors the module name), and keep names unchanged unless the task explicitly permits renaming.
- Add constructor parameters, method signatures, and return types to match expected usage; when Python typing is ambiguous, prefer the most permissive safe type (e.g., Option, Either, sealed trait hierarchies) but do not change required entrypoints.
- Step 4: Implement behavior incrementally with checkpoints
- Implement one logical component at a time (token types, data containers, tokenizers/dispatch, builders, helpers).
- After each component:
- Compile using the discovered build tool.
- Run any available unit tests or minimal runnable examples if present.
- Decision point: If behavior depends on Python dynamic dispatch, encode it explicitly in Scala (e.g., sealed trait + pattern match, or strategy objects) while keeping the external API unchanged.
- Step 5: Verifier-alignment checks before finalizing (execution anchor)
- Run a symbol inventory over the produced Scala files:
- Search for each required class/trait/object/def name and confirm it exists in the intended scope (top-level object vs class vs companion).
- Confirm there are no accidental renames (camelCase vs snake_case) for verifier-called entrypoints unless explicitly required by the contract.
- If any symbol is missing or in the wrong scope, fix structure first (do not patch by adding aliases unless you can guarantee they preserve behavior and do not conflict).
- Only then run the official verifier/test harness.

## Constraints / Pitfalls
- Do not add or recommend third-party Scala libraries unless the repository build files already declare them; otherwise default to Scala/Java standard library implementations to avoid environment mismatch.
- Do not change, omit, or "improve" the public API surface: required symbols (names, casing, and whether they are module-level vs class members) must remain exactly as specified; compilation success is insufficient without the post-write symbol/scope checklist.