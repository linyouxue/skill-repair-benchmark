---
name: fix-python-build
description: Diagnose and repair a Python repository whose build or test suite is broken. Use when a task asks to make a Python project's build/tests pass again, writes analysis notes to a failed_reasons file, proposes patch_{i}.diff files, and then applies them. Covers locating the project, reproducing the real CI failure, identifying code vs. configuration errors, producing clean git-style diffs, and verifying with the project's actual test entrypoint.
---

# Fix a Broken Python Build

A focused workflow for the recurring task shape:

> The repository is at `/home/<something>/build/failed/<repo>/<id>`.
> Step 1: analyse the failure and write notes to `failed_reasons.txt`.
> Step 2: write each change as `patch_{i}.diff` in standard git/GNU diff format.
> Step 3: apply those diffs to make the build pass.

Follow this playbook so you spend effort on the real failure rather than on
navigation or on malformed patches. Nothing in this skill is specific to a
particular repository — always re-derive the facts from the actual checkout.

---

## When to Use This Skill

Use it when the user prompt matches **all** of these cues:

- Describes a Python codebase with a broken build / failing tests.
- Points to a path that contains `build/failed/<repo>/<id>` (possibly with
  literal angle brackets that you must resolve).
- Asks for an analysis file (commonly `failed_reasons.txt`) and one or more
  `patch_{i}.diff` files, then asks you to apply them.

Do **not** use this skill when the user asks you to write new features, to add
new tests from scratch, or to repair infrastructure outside a single repo.

---

## Guiding Principles

1. **Reproduce before you theorise.** Run the project's real build/test command
   and capture the first failing error. Guessing without a stack trace wastes
   turns.
2. **Prefer minimal, focused fixes.** Do not restructure or reformat code. Do
   not pin new dependency versions "while you're there". Each `patch_i.diff`
   should address one concrete failure cause.
3. **Fix the real cause, not just the symptom.** A traceback pointing at an
   `ImportError` in module `A` is often caused by an unconditional import in
   module `B`. Follow the chain.
4. **Never claim a residual failure is "pre-existing" without evidence.** If
   additional tests still fail after your patch, either (a) show the failure
   predates your changes (e.g. via `git stash && rerun`, or git blame on the
   failing assertion), or (b) fix it as well. Build-fix tasks are usually
   judged on the test suite actually passing.
5. **Do not embed answers to this specific instance into any skill file.**
   Repair logic lives in the repo; skills describe the method.
6. **The deliverables are the scoring boundary.** The task is judged on three
   artefacts existing and being correct — the analysis note, the
   `patch_{i}.diff` file(s), and the applied fix. If anything goes wrong late
   (tests can't be installed, turns run out), those files must already exist
   on disk. Produce them *as you go*, not at the end.

---

## Pre-flight: Budget, Deliverables, and the Offline Case

Before you start exploring, internalise two realities that previous attempts
have tripped over:

**A. You have a finite iteration / wall-clock budget.** Treat exploration,
installation, and network troubleshooting as expensive. A rough target split:

- ~20% understanding the repo and the failure,
- ~10% attempting to reproduce,
- ~50% editing + producing and applying `patch_{i}.diff`,
- ~20% verification and any follow-up fix.

Concrete turn-based tripwires (apply even if you do not know the exact cap):

- **By turn 10** you should know the resolved absolute path, the CI command,
  and the first failure (or the regression commit if offline).
- **By turn 20** `failed_reasons.txt` must exist on disk as a first draft,
  even if it says "hypothesis under investigation".
- **By turn 30** `patch_1.diff` must exist and apply cleanly. If you are
  still reading source files at turn 30 with no patch on disk, **stop** and
  write what you have. A plausible patch you can refine beats a perfect
  patch you never write.
- **Reserve the last 20% of turns for verification and a second patch.**
  Do not use them for fresh exploration.

Previous attempts have run out of iterations with the first patch written
but the real test still red, because they spent the final turns chasing a
`ModuleNotFoundError` cascade in a micro-repro instead of either (a)
re-reading the regression diff for *other* behavioural changes they missed
or (b) using a pre-built venv that already had the test dependencies.

**B. The sandbox may be fully offline.** Many build-failure environments have
no PyPI access (proxy unreachable, DNS blocked, pip times out on every
request). In that case:

- You *cannot* `pip install -e '.[dev]'` and you *cannot* run the full test
  suite. That is fine — the task does not require you to run the tests, only
  to analyse, write diffs, and apply them.
- **Do not** burn turns on: alternate index URLs, HTTP proxy debugging,
  scavenging for wheels across the filesystem, trying `uv add`, looking for
  conda environments. One failed install attempt is a signal; two is a
  mistake.
- Pivot to **static analysis**: read `.github/workflows/*`, read the recent
  `git log` on `main` and especially the *last merge commit* (its diff is
  almost always the source of a newly-broken build), read the files in the
  traceback, read the tests to understand what behaviour is required.

A good heuristic: if `pip install` or `uv add` does not finish within a
minute, treat the environment as offline and move on. The right answer is
almost always discoverable from the git history and the source tree alone.

---

## Required Output Contract (produce these files, in this order)

1. `/home/<user>/build/failed/failed_reasons.txt` — your analysis and plan.
   Write a *first draft* as soon as you have a hypothesis; refine it later.
2. `<repo>/patch_1.diff`, `<repo>/patch_2.diff`, … — one git-style diff per
   logically-distinct fix, placed inside the resolved repo directory. Create
   each one *immediately* after making its edit (see Step 4). Do not batch
   patch creation to the end of the run.
3. The repository working tree with the patches applied. `git status` should
   show the changes, and `git apply --check` on each `patch_{i}.diff` from a
   clean tree must succeed.
4. The applied fix must actually make the build pass — graders typically
   re-run the real CI command after your patches apply. A diff that lands on
   disk but leaves a test red still scores zero for the build. The order of
   evidence you should trust, strongest first:
   1. The real CI command green on a pre-built interpreter (`cacher/env`,
      `.venv`, hostedtoolcache).
   2. `pytest --collect-only -q` clean + the file-of-first-error passing on
      that same interpreter (Step 5a).
   3. `python -c "import <pkg>"` clean + a micro-repro that mirrors the
      failing test's full import chain (Step 5b).
   A leaf-module micro-repro that skipped `import <pkg>` is **not** enough
   evidence on its own.

A missing or empty `patch_{i}.diff` is a hard failure even if the edit
itself is correct — the grader checks for the file. And a correct-looking
patch that still leaves the suite red is also a hard failure — do not stop
at "the diff looks right".

---

## Step 0 — Resolve the Angle-Bracket Path

The prompt frequently contains a *template* path like
`/home/github/build/failed/<repo>/<id>`. The literal `<repo>` and `<id>`
are placeholders you must resolve.

```bash
# List what's actually under the "failed" directory.
ls -la /home/github/build/failed 2>/dev/null \
  || ls -la /home/*/build/failed 2>/dev/null

# Find the first directory that looks like a Python project.
find /home/github/build/failed -maxdepth 4 -name pyproject.toml -o -name setup.py -o -name setup.cfg 2>/dev/null
```

Treat anything that is clearly scaffolding (a `cacher/env` virtualenv, a
`.cache` directory, etc.) as **not** the project. The project is the directory
that holds the source tree, a `.git`, and a packaging file.

Record the resolved absolute path and use it consistently — do not mix
`<repo>/<id>` placeholders into later paths or into the diff file names.

---

## Step 1 — Map the Build

Before running anything, read the metadata so you know what "the build" means
for this project.

```bash
# Packaging + declared dependencies.
sed -n '1,120p' pyproject.toml 2>/dev/null
sed -n '1,120p' setup.cfg      2>/dev/null
sed -n '1,120p' setup.py       2>/dev/null

# Primary test entrypoint.
sed -n '1,60p'  tox.ini        2>/dev/null
sed -n '1,60p'  noxfile.py     2>/dev/null
sed -n '1,60p'  Makefile       2>/dev/null

# What CI actually runs — this is the ground truth.
ls .github/workflows 2>/dev/null
for f in .github/workflows/*.yml .github/workflows/*.yaml; do
  [ -f "$f" ] && { echo "=== $f ==="; sed -n '1,120p' "$f"; }
done
```

Key things to note:

- The **declared** dependencies (`[project] dependencies`, `install_requires`).
- The **optional-dependency extras** (`[project.optional-dependencies]`,
  `extras_require`). An extra listed here is *not installed by default*.
- The **test command** used in CI (e.g. `tox`, `pytest`, `coverage run -m
  pytest`, `make test`). Prefer that command for your reproduction — not just
  a bare `pytest` that might miss what CI actually runs.
- The **supported Python versions** and whether the CI matrix differs from the
  interpreter in your sandbox.

---

## Step 2 — Reproduce the Failure Deterministically (Or, If Offline, Reconstruct It)

### Step 2a — Try one install + one test run (time-boxed)

Attempt the CI install + command *once*, with a short timeout, and capture
the full first failure, not only the summary line.

```bash
# Time-boxed install attempt. If it hangs or times out, STOP — treat as offline.
timeout 60 python -m pip install -e '.[dev]' 2>&1 | tee /tmp/install.log

# Reproduce CI exactly, with a timeout.
# If tox.ini defines envlist, call the one CI runs:
timeout 300 tox -e py312 2>&1 | tee /tmp/build.log

# Or the CI command directly, if tox isn't available:
timeout 300 coverage run --source <pkg> -m pytest 2>&1 | tee /tmp/build.log

# Or plain pytest as a fallback:
timeout 300 python -m pytest -x --tb=short 2>&1 | tee /tmp/build.log
```

If any of those succeed, read the log top-down — the *first* error is
almost always the only one that matters; later errors are typically cascades
from the first.

Before you give up on install, do one quick, bounded hunt for an environment
that *already* has the test dependencies installed (these are very common in
build-fix sandboxes and cost almost nothing to probe):

```bash
# Cached virtualenv shipped alongside the project (very common).
ls /home/*/build/failed/cacher/env/bin/python 2>/dev/null \
  /home/*/build/failed/*cache*/bin/python     2>/dev/null \
  /home/*/build/.venv/bin/python              2>/dev/null

# Hosted toolcache Pythons (GitHub-Actions-style runners).
ls -d /opt/hostedtoolcache/Python/*/x64/bin/python* 2>/dev/null | head -3

# Any python in $PATH other than /usr/bin/python.
command -v python python3 python3.10 python3.11 python3.12 2>/dev/null

# For each candidate, check whether pytest and (optionally) the specific
# test-time dependencies the project declares import. One line, one
# candidate — do not loop forever. Replace <extra_dep> with a dep you saw
# in pyproject.toml / tox.ini (e.g. the project's main test plugin).
for PY in /home/*/build/failed/cacher/env/bin/python \
          /opt/hostedtoolcache/Python/*/x64/bin/python3 \
          python3; do
  [ -x "$PY" ] || continue
  "$PY" -c "import pytest; print('$PY OK')" 2>/dev/null && break
done
```

If a candidate reports `OK`, use it for the test run — it is already live and
needs no `pip install`. Even if it is missing one package, a time-boxed
`"$PY" -m pip install --no-deps <missing>` against that specific interpreter
often succeeds where a blind global `pip install` does not, because the
interpreter was pre-configured to reach the right index.

**When you find a working interpreter, run the real test command with it —
do not reinvent the harness.** The point of the venv hunt is to reach the
actual CI entrypoint, not to then write a hand-crafted micro-repro.

```bash
# Prefer invoking the CI entrypoint directly against the found interpreter.
# The venv already has pytest + the project's test-time deps.
PY=/home/<somewhere>/build/failed/cacher/env/bin/python
cd "$TARGET"

# Mirror the CI command from tox.ini / .github/workflows exactly:
timeout 300 "$PY" -m coverage run --source <pkg> -m pytest 2>&1 | tail -n 60
# or, if coverage is unavailable:
timeout 300 "$PY" -m pytest -x --tb=short 2>&1 | tail -n 60

# If a single third-party import fails, install just that one against this
# interpreter rather than reaching for a repro.
"$PY" -m pip install --no-deps <missing-dep> 2>/dev/null
```

Reach for the micro-repro in Step 5b only when neither the system
interpreter nor any pre-built venv can run the real test runner. A found
venv that can import `pytest` is almost always the fastest path to a real
pass/fail verdict on your patch.

Give the hunt a single pass (5–10 seconds). If nothing works, move on — do
not burn turns iterating.

### Step 2b — If install/network fails, reconstruct from the repo

If `pip install` times out, returns `ConnectTimeoutError`/`SSLError`, or
otherwise cannot reach an index, **do not keep retrying**. The sandbox is
offline and no amount of proxy fiddling will fix it this turn. Switch to a
read-only reconstruction of the failure, using only information already on
disk:

```bash
# 1. The most recent change is almost always the cause of a freshly-broken build.
git --no-pager log --oneline -20
git --no-pager show --stat HEAD            # what changed in the top commit?
git --no-pager show HEAD                   # full diff of the top commit
# If HEAD is a merge, also look at what each side introduced:
git --no-pager log --oneline HEAD^..HEAD^2 2>/dev/null
git --no-pager diff HEAD^1...HEAD^2 2>/dev/null

# 2. Read the files the top commit actually touched.
git --no-pager show --name-only HEAD

# 3. Read every file that appears in an import chain from the package entry point
#    (`<pkg>/__init__.py`) — the real breakage is usually here.
cat <pkg>/__init__.py
#   then each submodule that __init__ imports, in order.

# 4. Read the tests that CI runs so you know what behaviour the fix must preserve.
ls tests/
head -40 tests/*.py

# 5. Read the CI workflow so you know which command and Python version CI used.
cat .github/workflows/*.y*ml
```

A hand-rolled diagnosis built from the merge diff + the import chain + the
tests is enough to produce a correct `patch_{i}.diff` in almost every case
seen in this benchmark. You do not need a passing `pytest` run to write a
correct patch.

**Enumerate every behavioural delta in the regression commit before you
patch.** When the regression is a merge or a large refactor commit, the
*first* change you spot (usually the one closest to the failing test name)
is rarely the only one that matters. Read the commit diff end-to-end and
list every hunk that is *behavioural* (ignore pure whitespace/line-wrap
hunks). For each behavioural hunk ask:

- Does any attribute, method, or module-level name that was previously
  initialised at class/module import time still get initialised after the
  change? (A common regression: a `self._foo = None` line is deleted in
  `__init__`, but `self._foo` is still read in another method that later
  raises `AttributeError`.)
- Does any early `return`, exception, or guard clause now short-circuit a
  side-effect that other code relies on (field mutation on the argument,
  cache priming, background-worker registration, logger setup)?
- Did any required argument / keyword name on a public API change? Call
  sites in `tests/` will catch this.

Grep the whole repo for every symbol whose initialisation / definition the
commit removed. If a deleted `self._x = ...` line still has readers, your
patch must restore that initialisation (or remove the readers in the same
patch). A regression commit that breaks N places should map to a patch that
fixes all N, not just one — otherwise the build still fails on test M+1
even when test M passes.

Common failure categories to look for:

| Symptom (first error) | Likely cause |
|---|---|
| `ModuleNotFoundError: No module named 'X'` during **test collection** | A top-level import of `X` in a module that `__init__.py` imports unconditionally, while `X` is only declared as an *optional* extra. |
| `ImportError: cannot import name 'Y' from 'X'` | A dependency was upgraded past a rename/removal, or a downstream module expects a newer API than the pinned version. |
| `SyntaxError` on a file that worked elsewhere | Python version mismatch; the file uses syntax newer than the interpreter running the tests. |
| `AttributeError: '...' object has no attribute '...'` only in tests | Real code bug introduced in a recent commit, or a test helper out of sync with the production class. |
| `FileNotFoundError` for a resource under `tests/` | Missing `package_data` / `MANIFEST.in` entry, or a `cwd`-sensitive path. |
| Build backend errors (`setuptools.build_meta` failing) | Malformed `pyproject.toml`, missing build system requires, or a version string that is not PEP 440. |

For each category, decide whether to fix **code** (the import, the attribute,
the version pin) or **configuration** (the extras list, the `tox.ini` deps,
the workflow). Prefer whichever change is smallest and most local.

---

## Step 3 — Write `failed_reasons.txt` *Early*

Write it in the exact path the prompt specifies (commonly
`/home/github/build/failed/failed_reasons.txt`). Keep it short and useful to
your future self.

Write a *first draft as soon as you have a working hypothesis* — even if
you have not yet produced the patch. This guarantees that at least one of
the required artefacts exists if later turns are cut off. You can refine
the note after the patch applies.

Suggested template:

```text
Repository: <absolute path to the repo>

=== Failure summary ===
<The exact test command you ran, and the first error message + file:line.>

=== Root cause ===
<One or two paragraphs explaining why that error happens, with the chain
of imports or the code path involved. Distinguish code vs. configuration.>

=== Plan ===
<Numbered list of the smallest changes needed, with the files touched.
One entry per intended patch_{i}.diff.>

=== Verification ===
<How you will re-run to prove the fix works — the same command as above.>
```

Do **not** paste the entire source file contents into this note. Keep it to
the facts a reviewer needs.

---

## Step 4 — Produce `patch_{i}.diff` Files Correctly (Edit-Then-Dump, One At a Time)

This is where previous attempts most often go wrong, in two ways:

- Hand-crafted unified diffs with wrong hunk headers (`@@ -L,N +L,M @@`
  with miscounted `N`/`M`) fail `git apply` with "corrupt patch" and burn
  turns.
- The agent batches "write all the diff files" to the final turn, then runs
  out of iterations before any `patch_{i}.diff` reaches the disk. The grader
  checks for the file, not the live edit — a correct edit without a patch
  file still scores zero.

**The reliable workflow — apply it to every edit, immediately:**

1. Edit the file in place to its final content (use your editor; make the
   smallest possible change).
2. **Right away**, ask git to produce the diff for you and save it with the
   expected name, inside the resolved repo directory. This always yields a
   hunk header whose counts match reality, and it guarantees the artefact
   exists on disk before you do anything else.

```bash
# Immediately after each file edit, dump the diff.
# Use the repo's own path (the one you resolved in Step 0) for the patch file.
REPO=/home/github/build/failed/<resolved-repo>/<resolved-id>
git -C "$REPO" diff -- path/to/changed_file > "$REPO/patch_1.diff"

# For multi-file changes, prefer one patch per logical fix:
git -C "$REPO" diff -- path/to/file_a > "$REPO/patch_1.diff"
git -C "$REPO" diff -- path/to/file_b > "$REPO/patch_2.diff"

# Verify the patch file is non-empty — an empty file means `git diff`
# saw no change (wrong path, or edit undone) and the grader will fail it.
test -s "$REPO/patch_1.diff" || { echo "patch_1.diff is empty!"; exit 1; }
```

3. Sanity-check that the diff applies cleanly from a clean state:

```bash
cd "$REPO"
git stash                # park the live edits
git apply --check patch_1.diff && echo "patch_1 applies"
git apply patch_1.diff
# (and patch_2.diff, etc., in order)
```

4. Confirm the applied file matches what you intended (`git diff HEAD`).

If you ever reach this step and still have no `patch_1.diff` on disk,
**that is the one thing you must fix before doing anything else** — even
before re-running tests.

If you must hand-write a diff (e.g. no git available), follow these rules:

- Use the `diff --git a/path b/path` header + `---`/`+++` + `@@ -L,N +L,M @@`
  format exactly.
- `N` = number of lines in the **old** hunk body (context + removed).
- `M` = number of lines in the **new** hunk body (context + added).
- Lines starting with a single space are context; `-` removes; `+` adds.
- No trailing whitespace on `@@` lines; no CRLF line endings.

---

## Step 5 — Apply and Verify

Apply the patches in order and re-run the real CI command:

```bash
for p in patch_*.diff; do
  echo "=== Applying $p ==="
  git apply --check "$p" && git apply "$p" || { echo "FAILED: $p"; exit 1; }
done

# Re-run what CI runs.
tox -e py312 2>&1 | tail -n 40
# or
coverage run --source <pkg> -m pytest 2>&1 | tail -n 40
```

**Acceptance bar:** the command the CI workflow runs must succeed, or
documentably reach the same green state the last passing commit had. If some
tests still fail:

- Re-read the top failure, apply the same diagnose-and-patch loop.
- Only mark a residual failure as out of scope if you can show evidence that
  it predates any build/import breakage you fixed (for example,
  `git stash && git checkout <last-green-commit> && rerun` reproduces it).
  "It looks pre-existing" is not evidence.

### Step 5a — The minimum verification gate: can the runner even collect?

Before you ever accept a micro-repro as proof (Step 5b), answer one cheap
question: **does `pytest` still enumerate every test file without an
ImportError?** Collection runs `import` on every `test_*.py`, every
`conftest.py`, every `tests/**/__init__.py`, and (transitively) your package.
If any of those raises, the build fails *before any assertion runs*, so a
perfect fix to the originally failing assertion cannot save it. This is the
single most common reason a build-fix patch passes a hand-rolled repro and
still scores zero on the real grader.

Use `--collect-only` as a sub-second smoke test against whichever
interpreter imports `pytest` (typically the one you found in Step 2a):

```bash
# The candidate interpreter from Step 2a that already has pytest.
PY=/home/<somewhere>/build/failed/cacher/env/bin/python
cd "$TARGET"

# 1. Can the package itself import at all? (Catches __init__.py regressions
#    that a single-submodule micro-repro cannot see.)
"$PY" -c "import <pkg>; print('import ok')" 2>&1 | tail -n 20

# 2. Can pytest collect every test without import errors?
timeout 60 "$PY" -m pytest --collect-only -q 2>&1 | tail -n 60

# 3. Once collection is clean, run at minimum the file the failing test
#    lives in — not only the single originally-failing test — so you catch
#    sibling regressions introduced by your edit.
timeout 300 "$PY" -m pytest tests/<file_from_first_error>.py -x --tb=short 2>&1 | tail -n 60
```

A `--collect-only` pass is weaker than a full green run but *far* stronger
than any micro-repro: a collection error in a sibling test file or an
`__init__.py` / `conftest.py` import failure red-lights the whole suite, and
it is detectable here in one command.

If collection fails:

- An `ImportError` on `tests/<sub>/__init__.py` or `tests/<sub>/test_*.py`
  usually means the test imports an *optional* extra that is not installed
  in this env (e.g. an integration / plugin module). The fix is almost
  always in `<pkg>/__init__.py` or the plugin module: make the optional
  import conditional (`try: import <x>; except ImportError: <x> = None`),
  or skip the dependent tests (`pytest.importorskip("<optional_dep>")` at
  the top of the test file), or add an `__init__.py`-level guard that
  avoids importing the handler until it is used. Decide by reading the
  pre-regression version of the same file — the correct shape is almost
  always visible there.
- An `ImportError` on the package itself means your fix is interacting with
  the entry point in a way a submodule-only micro-repro did not exercise.
  Re-read `<pkg>/__init__.py` and every submodule it touches at import
  time; the regression you are fixing may have a *second* behavioural
  change that only shows up when the package is imported as a whole.

If no interpreter in the environment can run `pytest --collect-only` at all,
still make the first check — `python -c "import <pkg>"` — on the plain
system interpreter. A patched file that cannot even be imported is never a
successful build.

### Step 5b — If no test runner is available, verify by execution-trace and micro-repro

Static analysis is enough to *write* a patch but not enough to *prove* it.
When the real test runner cannot be installed, do both of the following
before you call it done:

**1. Execution-trace every test the regression commit might have touched.**
After your edit is applied, read each affected test end-to-end and walk
through it against the *patched* source, line by line, like a debugger:

- Enumerate the tests to simulate: every test under `tests/` whose name
  mentions a symbol you changed, plus every test in the same file as any
  test the first error named, plus every test that calls the module you
  edited (`grep -R "<symbol>" tests/`).
- For each test, track object state across `setup_method`, fixtures, and
  statements. Pay particular attention to **singleton / module-level state**
  that persists across tests (a `@singleton` class, a module-level cache,
  `__init_subclass__`, atexit handlers). Previous attempts have passed the
  one test they focused on but broken a sibling test that shared singleton
  state.
- At each `assert`, confirm the condition is true with the patched code. If
  you cannot prove it is true without re-reading the source, assume it is
  *false* until you can.

**2. Write a tiny standalone Python repro and run it with the plain system
interpreter.** A micro-repro is the *last-resort* evidence channel, not a
substitute for Step 5a. Treat it as valid proof only when both of these are
true:

- You have already run `python -c "import <pkg>"` against the patched tree
  and it succeeds. A green micro-repro on a package that cannot import is a
  false positive — the real runner will fail at collection time.
- Your repro imports the same chain the failing test imports (via
  `import <pkg>` + the public API the test uses), not just the one leaf
  submodule you edited. Reaching into `<pkg>.<submodule>` directly skips
  the entry-point side-effects (singleton construction, optional-extra
  imports, module-level registration) that the real test would trigger.

You almost never need pytest for this — just enough of the
test body to exercise the failing assertion.

```bash
cat > /tmp/repro.py <<'PY'
# Reproduce only the failing assertion, with the minimum stubs needed.
# Do not import heavy optional test-only deps (HTTP mockers, coverage
# tooling, async libraries, etc.) — patch them out or skip the branches
# that need them.
import sys, time, types
sys.path.insert(0, "/home/github/build/failed/<repo>/<id>")

# Pre-populate sys.modules with stubs for every third-party import the
# package entry point pulls in transitively, so you do not hit a cascade of
# ModuleNotFoundError while trying to import <package>.  Stub only the
# symbols your repro actually dereferences — do not try to emulate the
# library.  Fill the tuple from the project's own declared dependencies
# (pyproject.toml / requirements.txt) and from the first few traceback
# frames, not from guesswork:
for name in ("<dep1>", "<dep2>", "<dep3>.<submod>"):
    sys.modules.setdefault(name, types.ModuleType(name))
# If a specific attribute on a stubbed module is read at import time, give
# it a trivial callable/sentinel so the import does not crash:
# sys.modules["<dep3>.<submod>"].<Attr> = lambda *a, **kw: None

# ... minimal setup that mirrors tests/test_X.py ...
import <package> as pkg
<run the code path>
assert <the condition the failing test checks>, "still broken"
print("repro OK")
PY
python3 /tmp/repro.py
```

If the repro passes, your patch likely fixes the real failure. If it fails,
your patch is wrong — iterate before you declare success. Delete the repro
when you are done so it does not pollute the final working tree.

**Hard stop on ModuleNotFoundError cascades.** If you fix one missing
dependency in the repro and the *next* turn surfaces a new missing one,
and the next after that, you are almost certainly on the wrong tool:

- If a pre-built venv (`cacher/env`, `.venv`, hostedtoolcache) exists, use
  **its** interpreter instead of `/usr/bin/python`; it will already have
  the whole dependency closure. A `PYTHONPATH="<repo>:…"` prefix plus the
  venv's `python` almost always resolves the cascade in one shot.
- Otherwise, switch the repro to stub *every* third-party module via
  `sys.modules.setdefault(name, types.ModuleType(name))` at the top of the
  file, **before** the first `import <package>` line. Two or more import
  failures in a row means you should widen the stubs, not chase them one
  at a time.
- If you have consumed two turns on a cascade with no progress, abandon
  the repro entirely and fall back to the pure execution-trace check in
  step (1) above. Chasing missing stdlib-adjacent deps turn after turn is
  one of the top causes of iteration-budget exhaustion with no final
  verification of the patch.

### Step 5c — Prefer a minimal revert / minimal shim over a rewrite

When the failure traces to a specific commit (very common: the merge at
`HEAD`), the *smallest* fix is almost always a localised restoration of the
previous behaviour at the exact call site that broke, not a refactor of the
surrounding function.

- Read the pre-regression version of the function:
  `git --no-pager show <parent-sha>:<path>` where `<parent-sha>` is the
  parent on the main branch (typically `HEAD^1` for a merge).
- Compare the pre- and post- versions side by side. The delta that caused
  the breakage is usually a few reordered or deleted lines. Restore
  *exactly* those lines and leave the rest of the new code alone.
- Resist the temptation to "improve" the function in the same patch — add
  new error handling, tighten types, consolidate branches, etc. Each such
  change is a new risk surface that can break a sibling test that was
  previously passing.
- If the new code was trying to fix a *different* bug (the commit message
  usually says so), keep that fix intact and only restore the specific
  behaviour the failing test depends on. One way: leave the new function
  structure, but reinstate the single expression / single early-exit
  position that changed.

---

## Anti-Patterns to Avoid

- **Running only `pytest`** when CI runs `tox` or `coverage run -m pytest`.
  Dependencies declared only under a `tox` env are missing from a bare
  `pytest` run and you can misdiagnose "missing dependency" as "test bug".
- **Marking unrelated tests `xfail` / `skip`** to make the suite green. The
  task is to fix the build, not to hide failures.
- **Upgrading or adding new third-party dependencies** to dodge an error
  unless the original dependency is genuinely broken and unavailable.
- **Reformatting or re-ordering imports** in files you did not need to touch.
- **Writing the fix inline in `failed_reasons.txt`** without producing an
  actual `patch_{i}.diff` and applying it.
- **Committing diffs that `git apply` rejects.** Always run `git apply
  --check` first.
- **Leaving stray debug files** (`patch.sh`, `scratch.py`, `*.bak`) in the
  repository.
- **Fighting the network.** If the first `pip install` hangs or times out,
  the sandbox is offline. Do not retry with a different index, a different
  proxy, `--trusted-host`, `uv add`, or by scavenging the filesystem for
  wheels. Pivot to static analysis from git history + the source tree.
- **Batching patch generation to the end.** Dump each `patch_{i}.diff`
  immediately after the edit that produced it, so the deliverable exists
  even if later turns are cut off.
- **Leaving `<repo>` / `<id>` placeholders in file paths.** Always resolve
  the template path from Step 0 before writing patches or notes.
- **Over-exploring.** Do not read every file in the repo. Read the files
  the top commit touched, the files in the first traceback, and the tests
  — stop there.
- **Declaring success from static analysis alone.** "The patch looks right"
  is not evidence; a plausible-looking patch that reorders control flow or
  tightens a condition can still break a sibling test. Either run the real
  test command, or build the small execution-trace + micro-repro check from
  Step 5b before you consider the task done.
- **Refactor-plus-fix in one patch.** If you only need to restore one
  statement or move one early-return, do *only* that. New error handling,
  consolidated branches, extra `and self._x is not None` guards, renamed
  locals — any of those add new risk and often break a sibling test that
  used to pass. Keep the diff as small as humanly possible.
- **Ignoring singleton / module-level state across tests.** Many test
  suites share state via `@singleton`, module-level caches, or class
  attributes initialised at import time. A fix that is correct in isolation
  can regress when the suite runs in order. Trace the state across
  consecutive tests before you commit.
- **Leaving a working pre-built interpreter unused.** If you find a
  `cacher/env`, `.venv`, or hostedtoolcache Python that imports `pytest`,
  use *that* interpreter to run the CI command. Do not fall back to a
  hand-written micro-repro when you already have a live test runner within
  reach — the real runner is more trustworthy than any stubbed repro.
- **Chasing ModuleNotFoundError one at a time in a micro-repro.** The
  moment the second missing module appears, widen the `sys.modules`
  stubs to cover *all* transitive third-party imports at once, or switch
  to a pre-built venv. Burning turns on a cascade is a top cause of
  running out of iterations before verification completes.
- **Patching only the first behavioural hunk you see in a regression
  commit.** Merge / refactor commits frequently change several behaviours
  at once (a deleted `self._x = None` in `__init__`, a reordered early
  return, a renamed kwarg). If any one is unaddressed, the suite stays
  red and the build still scores zero. Enumerate every behavioural hunk
  and either fix each or prove it is harmless before you stop patching.
- **Trusting a leaf-module micro-repro over a `--collect-only` run.** A
  repro that `import <pkg>.<submodule>` directly bypasses the entry point's
  side-effects (singleton construction, optional-extra import guards,
  conditional handler registration). A patch that looks green under such a
  repro can still fail collection in the real runner. Always precede the
  micro-repro with `python -c "import <pkg>"` and, whenever `pytest` is
  importable, a `pytest --collect-only -q` smoke test — see Step 5a.
- **Running only the one originally-failing test, not its file.** Even if
  you cannot afford the full suite, the file the failing test lives in is
  cheap (`pytest tests/<file>.py -x`). Sibling tests in the same file share
  singleton state and setup fixtures, so they are the most likely tests
  your edit silently broke.
- **Ignoring the rest of the test tree when a patch is a function reorder.**
  A reorder of guards, early-returns, or side-effects can silently drop or
  double-count calls into a worker / queue / logger that *other* tests
  assert on (e.g. request counts, enqueue counts, callback invocations).
  Before you ship the patch, grep the whole `tests/` tree for the callers
  of the symbol you touched and verify by eye that each surviving assertion
  still holds.

---

## Quick Reference

```bash
# 0. Resolve path (never leave <repo>/<id> placeholders lying around)
TARGET=$(find /home -type d -path '*/build/failed/*/*' \
         -exec test -e '{}/.git' \; -print -quit)
cd "$TARGET"

# 1. Try to reproduce, time-boxed (use the CI command from .github/workflows or tox.ini).
#    If install hangs or fails to reach the index, stop and skip to step 2'.
timeout 60 python -m pip install -e '.[dev]' 2>&1 | tee /tmp/install.log
timeout 300 tox 2>&1 | tee /tmp/build.log \
  || timeout 300 python -m pytest -x 2>&1 | tee /tmp/build.log

# 2. Diagnose from the test log — follow the first ImportError / AttributeError.
grep -nE "Error|FAILED|ModuleNotFoundError" /tmp/build.log | head

# 2'. If 1 was offline, diagnose from git instead.
git --no-pager log --oneline -20
git --no-pager show HEAD                       # what the last commit changed
git --no-pager show --name-only HEAD           # files touched
cat <pkg>/__init__.py                           # entry-point import chain

# 3. Draft the notes NOW (even before the patch) so the deliverable exists.
$EDITOR /home/github/build/failed/failed_reasons.txt

# 4. Edit code minimally, then DUMP THE PATCH IMMEDIATELY after each edit.
$EDITOR <changed file>
git diff -- <changed file> > "$TARGET/patch_1.diff"
test -s "$TARGET/patch_1.diff"                  # fail loudly if empty

# 5. Apply from clean state and verify.
git stash
git apply --check "$TARGET/patch_1.diff" && git apply "$TARGET/patch_1.diff"

# 5a. Prefer the real CI command on any pre-built interpreter you can find —
#     a cached venv has the test deps and sidesteps offline pip entirely.
PY=$(ls /home/*/build/failed/cacher/env/bin/python 2>/dev/null | head -1)
if [ -n "$PY" ] && "$PY" -c 'import pytest' 2>/dev/null; then
  # MINIMUM gate before accepting any patch: package imports + pytest collects.
  "$PY" -c "import <pkg>" 2>&1 | tail -n 20
  timeout 60  "$PY" -m pytest --collect-only -q 2>&1 | tail -n 40
  # Then the file the first error lived in (catches sibling-test regressions):
  timeout 300 "$PY" -m pytest tests/<file-of-first-error>.py -x --tb=short 2>&1 | tail -n 60
  # Only then the full CI command:
  timeout 300 "$PY" -m coverage run --source <pkg> -m pytest 2>&1 | tail -n 60 \
    || timeout 300 "$PY" -m pytest -x --tb=short 2>&1 | tail -n 60
else
  timeout 300 tox 2>&1 | tail                   # only if tox is installed
fi

# 5b. If no interpreter can run the real suite, verify by micro-repro —
#     but first confirm the package itself still imports under the plain
#     system interpreter. A leaf-module import is NOT a substitute:
python3 -c "import <pkg>"                       # must succeed before 5b counts
grep -R "<symbol-you-changed>" tests/ 2>/dev/null
python3 /tmp/repro.py   # see Step 5b for template
```

Keep the loop tight: one diagnosis → one minimal patch (prefer a minimal
revert; see Step 5c) → dump the patch file → apply → verify (real runner or
micro-repro) → sibling-test walkthrough.
