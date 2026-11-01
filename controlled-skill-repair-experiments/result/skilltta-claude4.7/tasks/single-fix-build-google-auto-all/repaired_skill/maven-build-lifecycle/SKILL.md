---
name: maven-build-lifecycle
description: Use when reproducing and repairing Maven CI build failures, especially legacy multi-module builds and Maven Invoker integration tests.
---

# Maven Build Lifecycle — Legacy CI Repair Workflow

## Build-repair artifact contract

This benchmark requires both a diagnosis artifact and an applicable patch.
The failed repository lives at `/home/travis/build/failed/<repo>/<id>` (for
example `/home/travis/build/failed/google/auto/<id>`). Always use the
`<repo>/<id>` placeholders — never hardcode a single project path.

Before finishing:

1. Write a diagnosis note to `/home/travis/build/failed/failed_reasons.txt`
   recording: failing module path, failing goal, exact error excerpt, root
   cause classification (code vs. configuration), and the planned fix list
   (file → change). This file is the scratchpad for the patch step.
2. Create at least one non-empty standard unified diff at
   `/home/travis/build/failed/<repo>/<id>/patch_1.diff` (and `patch_2.diff`,
   `patch_3.diff`, … if more than one concern) containing the intended
   source/configuration change. Use `diff --git a/… b/…` headers so
   `git apply` accepts them.
3. Apply the patch(es) inside the repository, e.g.
   `cd /home/travis/build/failed/<repo>/<id> && git apply --whitespace=nowarn patch_1.diff`.
   Fall back to `patch -p1 < patch_1.diff` if the directory is not a git
   working tree.
4. Check `git diff` / `git status` and ensure the intended project file —
   not only the patch artifact — was changed, then re-run the reproduction
   command to confirm the fix.

## Minimal diagnostic sequence

```bash
cd /home/travis/build/failed/<repo>/<id>

# 1. Inspect toolchain & module layout
cat .travis.yml 2>/dev/null | sed -n '1,80p'
sed -n '1,120p' pom.xml
grep -nE '<module>|<java.version>|maven.compiler|requireJavaVersion' -r . --include=pom.xml | head -n 50

# 2. Reproduce the full build failure (continue past first error, verbose)
mvn -B -ntp -fae -e clean verify 2>&1 | tee /tmp/build.log

# 3. Narrow to the failing module once identified
mvn -B -ntp -e -pl <failing-module> -am verify 2>&1 | tee /tmp/build-module.log

# 4. For Invoker / nested test projects, re-run inside the nested pom
(cd src/it/<nested-project> && mvn -B -ntp -e verify) 2>&1 | tee /tmp/build-nested.log

# 5. Enumerate error signatures for the iterate-match-act loop
grep -nE '\b(ERROR|BUILD FAILURE|cannot find symbol|package .* does not exist|Could not resolve)\b' /tmp/build.log | head -n 40
```

## Toolchain selection

- Detect the required JDK first: check `.travis.yml` (`jdk:` list),
  root `pom.xml` for `maven.compiler.release` / `source` / `target`,
  and any `maven-enforcer-plugin` `requireJavaVersion` rule.
- Align the invoked JDK with the strictest constraint. If the repo pins
  Java 8 but `JAVA_HOME` points elsewhere, export the matching JDK before
  invoking Maven (`export JAVA_HOME=…; export PATH=$JAVA_HOME/bin:$PATH`).
- Prefer `maven.compiler.release` over separate `source`/`target` when
  editing modern builds; preserve the existing style when editing legacy
  builds to avoid cascading enforcer failures.
- If a `toolchains.xml` is referenced, do not introduce new JDK vendors —
  reuse what the environment provides.
- Keep the Maven version compatible with the repo: very old projects may
  require Maven 3.6.x behaviour (e.g. legacy `http` repositories); do not
  upgrade plugin versions beyond what the pinned Maven supports.

## Nested test projects & Invoker ITs

- Enumerate submodules via the parent `<modules>` block; nested test
  fixtures also live under `src/it/<project>/pom.xml` (Maven Invoker) or
  `src/test/resources/projects/…`.
- Nested poms often inherit versions from the parent `dependencyManagement`.
  Before adding a `<version>` to a nested dependency, check whether the
  parent already manages it — prefer fixing the parent once over editing
  every nested pom.
- Constrain edits to the failing nested module. Do not touch unrelated
  sibling modules or sample projects just because they share a parent.
- When reproducing, use `-pl <module> -am` to build only the failing path
  plus its upstream dependencies; use `-amd` only when you need to verify
  downstream consumers.
- For Invoker ITs, reproduce by running the invoker goal
  (`mvn -B -ntp -e invoker:run`) or by `cd`-ing into the nested project
  and running its own `mvn verify` — but keep patches scoped to the files
  the IT actually exercises.
- If a nested project uses annotation processors (AutoValue, AutoService,
  Dagger), prefer `maven-compiler-plugin`'s `<annotationProcessorPaths>`
  over `provided` scope so the processor jar is not shipped.

## General Maven lifecycle reminders

- Lifecycle phase order (default): `validate → compile → test → package →
  verify → install → deploy`. `clean` is a separate lifecycle; `site` too.
  Binding a plugin to the wrong phase is a common cause of "works locally,
  fails in CI" drift.
- `-fae` (fail at end) surfaces every failing module in one run — prefer it
  while diagnosing. Switch to `-ff` (fail fast) once you expect success.
- Use `-o` (offline) only after at least one successful online resolve;
  otherwise missing artifacts masquerade as code errors.
- `-pl <module>` restricts the reactor; combine with `-am` (also make
  upstream) or `-amd` (also make downstream) to keep the build minimal
  while still exercising real dependency wiring.
- `-B -ntp -e` is the standard CI triple: batch mode, no transfer progress,
  show stack traces. Always include them when capturing logs for the
  diagnosis note.
- Prefer `mvn help:effective-pom -pl <module>` to resolve where a version
  or plugin configuration actually comes from before editing.
- Keep edits minimal and justified by an observed error; every change in
  a patch should map back to a line in `failed_reasons.txt`.
