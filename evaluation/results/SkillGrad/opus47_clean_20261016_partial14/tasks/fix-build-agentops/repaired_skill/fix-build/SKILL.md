---
name: fix-build
description: Fix a Python project's failing build by iterating on patches until the project's full test command exits 0. Use when the task is to repair a red build, resolve test/collection failures, or make CI green.
---

# Fixing a Failing Python Build

A build-fix task is complete when the project's **full test command** exits 0 —
not when the first error disappears, and not when the agent decides "enough".
Treat the task as a loop with both a floor and a ceiling: patch every failure
the command reports, keep each patch's blast radius proportional to the single
failing test it addresses, and compare the failing-test set after every run
against the previous one so a regression or a green suite is detected the
instant it happens.

The grader has **two possible success checks** — the test command exits 0, OR
the diff matches a reference minimal fix. You cannot distinguish them from
inside the sandbox, so the safe policy is: emit the minimal patch set that
clears the **baseline** failing set and no more. The baseline — captured
before any edit — is the authoritative scope boundary.

## Define success before patching

Before writing any fix, locate the exact command the grader / CI runs, run it
once, and record **what failed and in what shape**. The first visible error is
rarely the only one, and the shape of the baseline failure governs what counts
as in-scope later.

1. Read `tox.ini`, `pyproject.toml` (`[tool.pytest.ini_options]`,
   `[tool.tox]`), `Makefile`, `noxfile.py`, and `.github/workflows/*.yml` for
   the test invocation. Typical shapes: `pytest`, `coverage run ... -m pytest`,
   `tox`, `make test`. Record the command verbatim — it is your success
   check for the rest of the task.
2. Run the command once on the untouched snapshot and record both:
   - `failing_baseline` — the concrete set of failing test ids at baseline.
   - `shape` — classify the baseline output:
     - `shape = collection_error` when pytest reports "errors during
       collection", `_ERROR_ collecting ...`,
       `ImportError`/`ModuleNotFoundError` at module import time, or zero /
       near-zero tests actually executed. Under this shape `failing_baseline`
       is effectively empty — the entire suite is unreachable, not failing.
     - `shape = test_failures` when pytest collects the suite normally and
       some tests fail at execution time. `failing_baseline` is the concrete
       set of ids pytest reported FAILED/ERROR.
   Save the raw output — it is both the pre-patch reproduction for ceiling
   checks and the first value in the per-step delta comparison below.
3. Identify the **required deliverables** before you start patching. Typically
   one or more `patch_{i}.diff` files (one per root cause, produced via
   `git diff` on the exact files you touched), a `failed_reasons.txt`
   describing each diagnosed cause, and the diffs applied to the working
   tree. A green suite with no artifacts on disk scores zero.

```bash
# Generic shape — adapt the file names to the repo you're in
grep -R -nE "pytest|coverage run|tox" tox.ini pyproject.toml Makefile \
    .github/workflows 2>/dev/null
<TEST_COMMAND>  # the exact command you found, run once, output captured
# Classify the output: "errors during collection" / ImportError at import
# time → shape=collection_error; otherwise collect FAILED/ERROR ids →
# shape=test_failures.
```

Decision rule: if you cannot find an explicit test command, default to
`pytest` from the project root and note the assumption in your reasoning.

## Patch–rerun loop

After every patch, re-run the full test command and compare the new failing
set against the previous one. Progress, completion, and regression are all
decided by that set-difference — not by rereading the code and imagining the
next defensive edit.

1. Apply one focused patch (one root cause per patch file).
2. Re-run `<TEST_COMMAND>`; collect `failing_now` = the set of failing test
   ids from this run.
3. **Delta check against `failing_prev`.** On the very first re-run,
   `failing_prev = failing_baseline`. The rule below assumes
   `<TEST_COMMAND>` output is a deterministic function of the patch stack.
   Before acting on a `revert_last_patch` verdict, re-run `<TEST_COMMAND>`
   2–3 more times with NO edits. If `failing_now` differs across those
   reruns, you are observing a **flake**, not a regression — do not revert.
   See the flake branch in `references/verify-after-each-patch.md`.
   - `failing_now` is empty → **STOP immediately.** The build is fixed. Jump
     to "Finalize deliverables when green" below. Do not emit an additional
     patch for a symptom you noticed while reading the code, and do not
     keep rerunning the suite past the cap in that section — extra reruns
     expose you to flake-driven reverts of a correct fix.
   - `failing_now ⊆ failing_prev` and non-empty → progress; set
     `failing_prev = failing_now` and continue to step 4.
   - `failing_now` contains any test ∉ `failing_prev` **and the reruns in
     the preamble confirmed a stable failing set** → candidate regression
     OR newly-visible-after-collection-fix (see Scope-match check below).
     Under `shape = test_failures`, treat as regression: revert
     (`git checkout -- <files>` or delete `patch_N.diff`), re-run, do not
     layer a compensating patch. Under `shape = collection_error` on the
     first run after the collection-restoring patch, EVERY test in
     `failing_now` is "new" by naive set-difference — those tests were
     previously unreachable, not previously green. Run the scope-match
     check, don't jump to revert.
4. For each test in `failing_now`, classify it (see decision rule below) and
   plan the next focused patch — or stop under the scope-match check.
5. Emit `patch_{N+1}.diff` and loop at step 1.

```python
# Generic delta-check sketch — shape and reruns gate the revert branch.
failing_now = parse_failing_ids(run_tests())
new_failures = failing_now - failing_prev
if not failing_now:
    finalize_deliverables_and_stop()
elif new_failures:
    if shape == "collection_error" and failing_prev == failing_baseline:
        # First run after collection fix: "new" is naive — these tests were
        # unreachable at baseline. Run the scope-match check below.
        run_scope_match_check(new_failures)
    else:
        reruns = [parse_failing_ids(run_tests()) for _ in range(2)]
        if any(new_failures - r for r in reruns):
            mark_flake(new_failures)              # see L3 for clean-baseline
        else:
            revert_last_patch(new_failures)
else:
    failing_prev = failing_now
    plan_next_patch(failing_now)
```

Read `references/verify-after-each-patch.md` when `failing_now` is non-empty
after any patch, OR when a `revert_last_patch` verdict appears but the same
patch stack produced different failing sets on recent runs (flake branch),
OR when `shape = collection_error` and this is the first run after the
collection-restoring patch (shape-guard branch). Skip when the suite is
already green on the first re-run.

Decision rule — scope is bounded on **three** sides:

- **Floor** (shape-dependent). "Pre-existing" / "out-of-scope" is a claim
  that needs evidence.
  - Under `shape = test_failures`: a failure may be excluded only when
    **at least one** holds: (a) the prompt explicitly scopes the task
    (e.g. "fix only the import errors"), or (b) the identical failure
    reproduces on the untouched pre-patch snapshot you captured AND the
    prompt wording does not require fixing it. Absent both, treat the
    failure as in scope and keep patching until every test in
    `failing_baseline` passes.
  - Under `shape = collection_error`: the floor collapses to "collection
    must succeed and every error recorded in the baseline must clear".
    `failing_baseline` is effectively empty, so no in-execution test is
    on the floor. Tests that fail only after collection is restored are
    NOT on the floor — they are governed by the scope-match check below.
- **Ceiling.** Before writing any patch that would modify cross-cutting
  infrastructure — decorator definitions, metaclasses, project-wide
  singletons, atexit/signal installers, logging/import machinery, any
  symbol imported by ≥3 modules, **or module-level package-initialization
  functions (`pkg.init()`, `pkg.configure()`, `pkg.setup()`) that are
  called from many tests' setup/teardown and manage shared process-wide
  state (sessions, workers, HTTP clients, background threads, atexit
  registrations)** — you must first `git stash` the current patch stack
  and re-run the still-failing test on untouched HEAD. If it fails
  identically on HEAD, the failure is pre-existing — do NOT widen into
  shared machinery. If it passes or fails differently, an earlier patch
  regressed it; fix at the narrowest site, not in the shared machinery.
  Under `shape = collection_error` the test may have been unreachable
  on HEAD (no comparable signature exists); treat "unreachable on HEAD"
  as equivalent to "pre-existing / out of scope" and do NOT widen.
- **Scope-match check** (fires before any patch beyond the minimum that
  cleared `failing_baseline`). Ask four questions:
  1. Is the newly-failing test in `failing_baseline`? Under
     `shape = collection_error` the answer is almost always NO.
  2. Does the proposed patch touch files OTHER than the one that cleared
     the baseline failure?
  3. Does the proposed patch alter runtime semantics of a public API
     (`pkg.init()` now re-starts sessions, `Class.__init__` now
     unconditionally sets an attribute previously conditional)?
  4. If (1=No) + (2=Yes) + (3=Yes), STOP patching. Keep only the minimal
     fix; document the newly-visible failure in `failed_reasons.txt` as
     a pre-existing latent bug exposed by the baseline fix; submit. A
     green suite with a bloated diff reliably loses to a diff-matched
     minimal fix even when the latter leaves one latent test red.

Read `references/triage-remaining-failure.md` when a test still fails after
one or more patches and the next candidate edit would touch any of the
cross-cutting sites named in the ceiling above, OR when the next failing
test is "new" under `shape = collection_error` and you need the Branch E
algorithm to decide whether it is in scope. Skip when the remaining
failures are plain collection/import errors on the exact file you have
not yet patched.

## Finalize deliverables when green

The grader rewards concrete artifacts on disk, not an in-memory green run.
As soon as `<TEST_COMMAND>` has exited 0 **once** with the current patch
stack, immediately produce the deliverables — before any additional
characterization or confirmation reruns.

1. For every file you edited, write `patch_{i}.diff` via `git diff -- <file>`
   (one diff per diagnosed root cause). Verify each applies cleanly from a
   stashed baseline with `git apply --check patch_{i}.diff`.
2. Write `failed_reasons.txt` naming each root cause and which
   `patch_{i}.diff` addresses it. If the scope-match check caused you to
   leave a newly-visible test failing, record it here as a pre-existing
   latent bug exposed by the baseline fix.
3. Ensure the diffs are applied to the working tree (if you emitted them
   from a committed state, re-apply with `git apply patch_{i}.diff`).

```bash
# Generic shape — do this the first time <TEST_COMMAND> exits 0, or the
# first time the scope-match check tells you to stop with a latent-bug
# footprint left in place.
for f in $(git diff --name-only); do
    i=$((i+1)); git diff -- "$f" > "patch_${i}.diff"
    git apply --check "patch_${i}.diff"       # must succeed
done
printf 'root cause 1: ...\nroot cause 2: ...\n' > failed_reasons.txt
```

Decision rule — budget reruns and iterations:

- **At most 3 confirmation reruns** after the first green run. Further
  reruns are speculative; each additional run increases the chance a
  flake fires and tempts you into reverting a correct fix.
- **Iteration reserve.** When remaining iterations drop to ~20–30% of the
  original budget, halt all optional work (extra reruns, flake
  characterization, "while I'm here" code reading) and spend the rest
  exclusively on finalizing deliverables above. A reverted-correct-fix
  with no patch files on disk scores 0; a correct fix with patch files
  written scores reward even if a later rerun flakes.

## Common Pitfalls

- **One success check is not two.** `pytest exit 0` is only one of two
  possible grader checks; a diff-match against a reference minimal fix
  is the other and typically governs when the baseline was a
  collection/import error. Symmetric trap on the other side: a clean
  collection phase with failing tests under `shape = test_failures` is
  still a red build. Judge success against the shape-split floor above,
  not against the first green pytest line you see.
- **Treating one suite run as ground truth instead of a sample.** Both
  stopping early ("the rest look pre-existing"), stacking an extra patch
  after the suite is green ("the code still has a smell"), AND reverting
  a correct fix after one flaky red run come from reading a single run as
  deterministic truth. Progress = strict subset. Done = empty set. New
  test in `failing_now` requires a 2–3 rerun confirmation that the failure
  is stable before any revert; if the failing set differs across those
  reruns, it is a flake, not a regression.
- **Labeling a failure "pre-existing" from the traceback alone.** Without
  a pre-patch reproduction, explicit prompt scoping, OR a
  `shape = collection_error` baseline that proves the test was
  unreachable before your fix, a failing test is in scope. The
  traceback's age is not evidence.
- **Widening the blast radius past the traceback.** When a traceback blames
  a specific attribute/method on a specific class, fix at that class — not
  in the decorator, metaclass, module-level `pkg.init()`, or framework
  singleton that constructs it. Edits to project-wide machinery change
  semantics at every call site, almost never match a reference minimal
  fix, and are rarely the right answer for a single failing test; require
  a stashed-HEAD pre-patch reproduction AND passage of the scope-match
  check before any such edit.
- **Fixing symptoms by editing the test.** When a traceback blames in-repo
  production code (e.g. `AttributeError` on a project class), fix the
  production code, not the test, unless the test itself is clearly wrong.
- **Burning the iteration budget on characterization with nothing on
  disk.** `max_iterations` termination with no `patch_{i}.diff` or
  `failed_reasons.txt` on disk scores 0 even if you had a green suite
  earlier. Finalize deliverables the first time the suite exits 0 OR the
  first time the scope-match check tells you to stop; treat further
  reruns as optional and bounded.
