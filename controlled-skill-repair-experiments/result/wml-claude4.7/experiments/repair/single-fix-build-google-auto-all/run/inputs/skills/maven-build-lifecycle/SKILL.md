---
name: maven-build-lifecycle
description: Use when reproducing and repairing Maven CI build failures, especially legacy multi-module builds and Maven Invoker integration tests.
---

# Maven Build Lifecycle — Legacy CI Repair Workflow

## Build-repair artifact contract

This workflow requires both a diagnosis artifact and an applicable patch.
Treat the task description as the source of truth for paths. The task will give
you a repository location of the form:

```
/home/travis/build/failed/<repo>/<id>
```

Resolve `<repo>` and `<id>` from the current task before running any command.
Do **not** hardcode any specific repository or build id (e.g., do not assume a
particular organization/project name). Everywhere the steps below reference
`<repo>` and `<id>`, substitute the values given by the task.

Before finishing, ensure that:

1. `/home/travis/build/failed/failed_reasons.txt` contains your diagnosis and
   remediation plan (written in Step 1 and consulted in Step 2).
2. At least one non-empty standard unified diff exists at
   `/home/travis/build/failed/<repo>/<id>/patch_1.diff` (increment the index
   `patch_2.diff`, `patch_3.diff`, … only if you genuinely need multiple
   patches). The diff must describe the intended source/configuration change.
3. The patch has been applied to the repository rooted at
   `/home/travis/build/failed/<repo>/<id>`.
4. `git -C /home/travis/build/failed/<repo>/<id> status` and
   `git -C /home/travis/build/failed/<repo>/<id> diff` confirm that the
   intended project file(s)—not only the `patch_*.diff` artifact—were changed.

## Minimal diagnostic sequence

All commands assume `<repo>` and `<id>` are the values from the current task.

```bash
# 1. Enter the failing repository (never hardcode a specific repo/id).
cd /home/travis/build/failed/<repo>/<id>

# 2. Select the build toolchain. Prefer the project-pinned Maven Wrapper
#    when it is present and executable, otherwise fall back to system mvn.
if [ -x ./mvnw ]; then
  MVN="./mvnw"
elif [ -f ./mvnw ]; then
  MVN="sh ./mvnw"
else
  MVN="mvn"
fi

# 3. Reproduce the failure to capture the real error signal. Use batch mode,
#    full errors, and fail-at-end so every module reports its first failure.
#    Adjust the lifecycle phase to match the project (compile / test / verify
#    / install). Record the output for the diagnosis note.
$MVN -B -e -fae -U clean verify 2>&1 | tee /tmp/mvn-build.log

# 4. Summarize the actionable errors (compiler messages, missing artifacts,
#    plugin failures, Invoker IT reports) into
#    /home/travis/build/failed/failed_reasons.txt before editing anything.
```

Only after the reproduction above yields a concrete error should you decide
whether the fix belongs in source code, a POM, or a plugin configuration.

## General Maven lifecycle reminders

- **Toolchain parity.** Use the same wrapper/version the CI uses. If `./mvnw`
  exists, invoking system `mvn` can mask or change the failure. Record which
  binary you used in `failed_reasons.txt`.
- **Reproduce before editing.** Never patch based on static reading alone;
  always confirm the failure signature from a fresh build log.
- **Use `-B -e -fae`.** Batch mode plus full error traces plus fail-at-end
  surface every module's first failure in one run, which is critical for
  multi-module projects.
- **Smallest viable patch.** Change the narrowest file that removes the error.
  Prefer POM/property fixes over source rewrites when the root cause is a
  dependency, plugin version, or Java/compiler setting.
- **Verify after applying.** Re-run the same reproduction command and confirm
  the previously failing goal now passes (or at minimum the targeted error is
  gone) before declaring the repair complete.

### Nested Maven Invoker IT projects (`src/it/*`)

Legacy multi-module builds frequently drive integration tests through the
`maven-invoker-plugin`, which executes each `src/it/<project>/pom.xml` as an
independent Maven build. When the failure originates in one of these nested
projects, scope the repair carefully:

1. **Locate the actual failing POM from the Invoker log.** The outer build
   log will reference a `build.log` under
   `target/it/<project>/` (or a configured `cloneProjectsTo` directory).
   Read that nested `build.log` to find the real error — the outer failure
   is only a wrapper.
2. **Understand version/plugin inheritance.** Nested IT POMs often rely on
   the outer build via `@project.version@` token filtering, an explicit
   `<parent>` reference, or `invoker.properties`. Before editing, determine
   whether the failing version/plugin configuration is defined:
   - inside the nested `src/it/<project>/pom.xml` itself,
   - in a parent POM referenced by the nested project, or
   - supplied by the outer build via the invoker plugin's `pomIncludes`,
     `settingsFile`, or filtered properties.
3. **Edit the smallest POM that fixes it.** If the fault is isolated to one
   IT scenario, patch only that `src/it/<project>/pom.xml`. Modify the outer
   parent POM only when the defect truly lives in shared configuration
   (e.g., a managed dependency/plugin version consumed by multiple ITs).
   Do not blindly rewrite the aggregator POM when a single invoker project
   is at fault.
4. **Preserve filtering tokens.** Keep `@...@` placeholders intact in
   `src/it/**/pom.xml` so the invoker plugin can still substitute them at
   runtime; replacing them with literal versions can break other ITs.
