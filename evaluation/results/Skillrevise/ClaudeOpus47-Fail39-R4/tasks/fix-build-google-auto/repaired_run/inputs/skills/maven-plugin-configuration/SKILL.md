# Maven Build Repair Workflow

## Purpose
Diagnose a failing Maven build, author minimal unified-diff patches, and verify the fix by re-running the exact CI command. Produces the task-mandated artifacts (failed_reasons.txt and patch_{i}.diff) rather than exploring configuration options.

## When to Use
Use when a task provides a broken Maven project plus a CI invocation and requires you to write a root-cause note and one or more patch diffs that make the build pass. Do NOT use for green-field plugin configuration advice or general Maven tutorials.

## Procedure
- Ground the environment. Record `java -version`, `mvn -v`, the project's `<source>/<target>/<release>` and `project.build.sourceEncoding`, and the CI invocation (phase, `-f` pom, profiles). Locate any provided CI log (e.g. under the project tree or `/home/travis/build/*.log`) and treat it as the ground-truth failure signature.
- Reproduce once with the exact CI command. Capture the first failing goal and the first error block verbatim. Write `failed_reasons.txt` at the task-specified path summarizing: failing module, failing goal, error signature, and identified root cause class (see decision table below). Stop exploring after one reproduction.
- Pick the minimal fix using this decision table, then write it as `patch_{i}.diff` at the task-specified path in standard unified-diff format (`diff --git` or `--- a/ +++ b/` headers, correct hunk offsets):
- `Could not find artifact com.sun:tools` on JDK >= 9: exclude the system-scope `com.sun:tools` transitive, or add a profile activated by `jdk=[9,)` that skips it.
- `unmappable character` / encoding warnings: set `project.build.sourceEncoding=UTF-8` (and `<encoding>` on compiler/resources plugins only if the property is ignored).
- `NoSuchMethodError` / missing class from a transitive (e.g. Guava `MoreObjects`): pin the correct version via `<dependencyManagement>` or add a direct dependency; do not shade.
- Plugin version drift / `MojoExecutionException` tied to a plugin: pin the plugin version in `<pluginManagement>`.
- Wrong JDK vs. source level: align `<release>`/`<source>`/`<target>` with the active JDK rather than switching JDK unless the task fixes the JDK. Prefer the smallest hunk that neutralizes the root cause; one patch per logically distinct fix.
- Apply and verify. Run the apply step defined by the task, then re-run the exact original CI command. Confirm: (a) `failed_reasons.txt` exists and is non-empty, (b) every `patch_{i}.diff` exists and parses as a unified diff, (c) the re-run reaches the previously failing phase and succeeds. If verification fails, inspect the new first-failure signature and loop back to step 3 with a bounded additional patch; do not restart from step 1.

## Constraints / Pitfalls
- Write artifacts only at the paths the task names; never silently relocate them. Perform an existence check on `failed_reasons.txt` and each `patch_{i}.diff` before declaring done.
- Patches must be valid unified diffs against the current tree; do not emit full-file rewrites or inline XML snippets.
- Do not change unrelated plugin configurations, bump versions globally, or add new plugins beyond what the root cause requires.
- Cap exploration: at most one reproduction run and at most one additional patch iteration after the first apply; if still failing, revise `failed_reasons.txt` with the residual signature rather than branching further.
- Never hardcode paths, JDK versions, or Maven versions from memory; read them from the actual environment and the task's CI command.