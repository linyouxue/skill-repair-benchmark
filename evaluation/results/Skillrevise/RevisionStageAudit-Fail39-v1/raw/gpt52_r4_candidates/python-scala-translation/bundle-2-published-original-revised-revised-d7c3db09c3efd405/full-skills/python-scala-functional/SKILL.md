# Python Module To Scala 2.13 Translation With Verifier-Aligned API Surface Audit

## Purpose
Translate a Python module into Scala 2.13 while preserving the verifier-visible public API exactly (required names, signatures, and placement/scope), using discovery-first setup and hard completion gates that prove the produced Scala exposes every required symbol.

## When to Use
Use when a task requires converting Python code to Scala and a verifier will check for specific public identifiers (classes/traits/objects/defs and specific method names). Especially use when the task provides an explicit "must include these symbols" list, or when prior attempts compiled but failed verification.

## Procedure
- 1) Discover repository and verifier-facing requirements (before coding)
- Locate the Python module(s) to translate and any existing Scala build layout (build.sbt, src/main/scala tree, package conventions).
- If the task provides a required symbol list, treat it as authoritative: record each required identifier and, if stated, its required scope (top-level vs inside an object/class/package).
- If output file path/package is not explicitly given, discover it from repo conventions; if still ambiguous, stop and request clarification rather than guessing.
- Check tool availability (scalac, scala, sbt). If none are available, you can still write source, but you must not claim compile-verified readiness.
- 2) Build an API inventory from the Python source (translation schema)
- Enumerate all Python top-level definitions: classes, functions, constants, and any module-level helpers that are part of public usage.
- For each class, list constructor args and public methods/properties.
- Build a single "Required API Checklist" that is the union of:
- Task-provided required symbol list (highest priority).
- Python inventory items that are clearly part of the module public API (lower priority unless task says "all").
- For each checklist item, record required name spellings exactly. Do not apply renaming conventions unless the task explicitly instructs them.
- 3) Decide Scala placement rules and naming rules (decision point)
- Placement rule:
- If the checklist requires a top-level function (eg "tokenize"), implement it as a top-level def in the package (Scala 2.13 allows package-level defs), or in an object only if the verifier contract explicitly expects that object.
- If scope/placement is not specified, prefer the closest Scala equivalent of the Python module surface: package-level defs and classes in the same package.
- Naming rule:
- Preserve exact required identifier spellings from the checklist.
- If the Python code uses snake_case but the required list includes camelCase (or vice versa), implement the required spelling and, only when needed for compatibility, add a thin alias for the other spelling. Do not delete or rename the required spelling.
- Type rule:
- Choose the simplest Scala types that allow typechecking and preserve call semantics. Avoid introducing extra wrapper types that would change call sites unless required.
- 4) Implement in two passes with compile checkpoints
- Pass A: Skeletons
- Create Scala declarations for every checklist symbol with correct names and intended scope: classes/traits/objects/defs with minimally typecheckable signatures.
- Do not fill in logic until all symbols exist at the intended visibility.
- Pass B: Semantics
- Implement behavior, prioritizing matching Python semantics over idiomatic refactors that could change observable behavior.
- Compile checkpoint (if tools exist):
- Compile after skeleton pass and after semantic pass; fix errors immediately.
- Do not use a successful compile as the final completion gate.
- 5) Mandatory verifier-aligned API surface audit (hard completion gate)
- Audit A: Static presence check
- Re-scan the produced Scala source files and confirm every checklist identifier appears as a declaration (class/trait/object/def) in the intended scope.
- If any required item is missing or appears only as a method when a top-level def is required, stop and repair placement (return to step 3/4).
- Audit B: Referenceability check (execution anchor)
- Create a tiny Scala "reference" snippet (in the same build context/package) that imports the produced package and:
- References each required class/object/def by name.
- Instantiates required types where possible.
- Type-checks calls to required methods (eg ensure a Token has withMetadata, ensure a type has toToken if required).
- Compile this snippet with the available toolchain.
- Only declare completion if the reference snippet compiles and the static presence check passes; otherwise, repair and re-run the audits.

## Constraints / Pitfalls
- Do not claim success based only on scalac/sbt compilation of the main file(s); completion requires the API surface audit plus a referenceability compile of all required symbols.
- Do not guess output paths, package names, or symbol placement when the task/repo does not specify them; discover from the repository or ask for clarification. If a required symbol list exists, do not rename or relocate those symbols for style or convention.