# Triaging a test that still fails after one or more patches

Read this when `<TEST_COMMAND>` still shows a failing test after your most
recent patch, AND either (i) the fix you are considering next would touch
cross-cutting infrastructure (decorator definitions, metaclasses,
project-wide singletons, atexit/signal installers, logging/import
machinery, any symbol imported by many modules, **or module-level
package-initialization functions (`pkg.init()`, `pkg.configure()`,
`pkg.setup()`) that are called from many tests' setup/teardown and manage
shared process-wide state (sessions, workers, HTTP clients, background
threads, atexit registrations)**), OR (ii) the baseline was a
`shape = collection_error` and the still-failing test only became visible
AFTER the collection-restoring patch (Branch E below). The whole point of
this reference is to stop you from emitting that patch on a hunch.

If the suite was green on this run or your last patch introduced a NEW
failing test (and shape ≠ collection_error), this is the wrong reference —
read `references/verify-after-each-patch.md` instead for the stop / revert
branches.

The branched algorithm below separates five possibilities you cannot tell
apart from the traceback alone:

1. The failure is **pre-existing** on untouched HEAD → stop, do not widen.
2. The failure is a **regression** introduced by one of your own patches →
   fix at the narrowest site inside the file you touched (or revert).
3. The failure is a **genuine next in-scope bug** with a local fix → patch
   at the class/function the traceback names (not its decorator).
4. The failure genuinely implicates cross-cutting machinery → only now may
   you edit the decorator/singleton/handler/package-init, and only with
   the pre-patch reproduction recorded as justification.
5. The failure is **newly visible after a collection fix** → treat as a
   pre-existing latent bug, do NOT widen and do NOT revert the collection
   fix.

## Step 1 — Capture the current failure signature

Save the exact failing test id and the top of its traceback before you touch
anything. You will compare against this when you re-run on HEAD.

```python
import re, subprocess

TEST_CMD = ["<TEST_COMMAND>"]  # the exact command from SKILL.md step 1
RESULT = subprocess.run(TEST_CMD, capture_output=True, text=True)

# Grab (test_id, first exception line) pairs
pattern = re.compile(
    r"^(FAILED|ERROR) (\S+)(?:.*?\n)+?.*?^E\s+(\w+(?:Error|Exception)):?\s*(.*)$",
    re.MULTILINE,
)
with_patches = {
    m.group(2): (m.group(3), m.group(4).strip())
    for m in pattern.finditer(RESULT.stdout + RESULT.stderr)
}
print("still failing WITH my patches:", with_patches)
```

## Step 2 — Stash your patches and re-run just those tests on HEAD

```bash
git stash push -u -m "fix-build:triage"            # park every uncommitted edit
<TEST_COMMAND> -k "<the failing test id or ids>"   # or re-run the full suite
echo "exit=$?"
git stash pop                                      # restore your patches
```

Then capture the HEAD-side signatures the same way:

```python
on_head = {
    m.group(2): (m.group(3), m.group(4).strip())
    for m in pattern.finditer(HEAD_RESULT.stdout + HEAD_RESULT.stderr)
}
```

Note: if `shape = collection_error` at baseline, `on_head` will be empty or
contain only the collection-error ids — the real test bodies never ran on
HEAD. Jump to Branch E in Step 3 for those tests rather than reading
`head_sig is None` as "regression".

## Step 3 — Branch on the comparison

```python
for test_id, sig in with_patches.items():
    head_sig = on_head.get(test_id)
    if head_sig == sig:
        # Branch A: identical failure on untouched HEAD → PRE-EXISTING
        verdict[test_id] = "pre_existing"
    elif head_sig is None and shape == "collection_error" and \
            test_id not in failing_baseline:
        # Branch E: test was UNREACHABLE on HEAD because collection failed.
        # The collection-restoring patch did not CAUSE this failure; it
        # merely made the test reachable. Treat as pre-existing latent bug.
        verdict[test_id] = "pre_existing_latent"
    elif head_sig is None:
        # Branch B: passes on HEAD → REGRESSION from your own patches
        verdict[test_id] = "regression"
    else:
        # Branch C: fails differently on HEAD → partially regressed; treat
        # as regression at the file your most recent patch touched
        verdict[test_id] = "regression_partial"
# Branch D (implicit): if a test shows up only after your patches and
# traceback names shared machinery, it is still a regression, not a
# license to edit the decorator — fix at your own patch site first.
```

Act on the verdict:

- **pre_existing** → Do NOT widen the patch into shared machinery. Record
  the HEAD-side traceback as evidence and stop patching this test. The
  grader's floor rule in SKILL.md still applies: only skip if the prompt
  does not require fixing it; otherwise document the blocker and stop
  rather than emit a cross-cutting edit.
- **pre_existing_latent (Branch E)** → Keep the minimal
  collection-restoring patch exactly as it is; do NOT revert it, and do
  NOT add any further patch to make this newly-visible test pass. Edits
  to `pkg.init()`, `Class.__init__`, singletons, or session machinery to
  paper over the latent bug reliably overshoot the grader's reference
  diff and lose. Record the failing test id and its traceback in
  `failed_reasons.txt` as "pre-existing latent bug exposed by the
  collection fix; outside the reference diff for this task", then jump
  to SKILL.md "Finalize deliverables when green".
- **regression / regression_partial** → Open the patch file you most
  recently emitted. Revert it or fix inside that file. Do not edit a
  decorator, metaclass, or module-level `pkg.init()` to compensate for a
  local mistake.
- **genuine next bug with local fix** (verdict absent because the test did
  not exist in `with_patches` before your latest patch, or your triage
  shows the traceback names a plain class attribute/method): patch at the
  named class. This is the normal in-scope loop; you did not need this
  reference for it.
- **cross-cutting edit truly required**: only reachable when the traceback
  itself names the decorator/metaclass/handler/package-init AND the test
  is not pre-existing AND no narrower site exists. Keep the diff minimal;
  do not change call-count semantics (e.g. "re-invoke `__init__` on every
  call", "unconditionally reset `_session`/`_worker` inside `pkg.init()`")
  unless the test explicitly asserts that behavior.

## Step 4 — Verification before the next patch

After acting on the verdict, re-run `<TEST_COMMAND>` and check:

```python
assert "pre_existing" not in verdict.values() or scope_documented, (
    "If any verdict is pre_existing you must have recorded the HEAD-side "
    "traceback and either (a) prompt-scope evidence or (b) a stop decision. "
    "Otherwise go back to Step 2."
)
assert "pre_existing_latent" not in verdict.values() or latent_documented, (
    "If any verdict is pre_existing_latent you must have recorded the test "
    "id in failed_reasons.txt as a latent bug exposed by the collection "
    "fix, AND you must NOT have emitted an additional patch to make it "
    "pass. Otherwise go back and remove that extra patch."
)

post = subprocess.run(TEST_CMD, capture_output=True, text=True)
post_failing = {m.group(2) for m in pattern.finditer(post.stdout + post.stderr)}

# Corrective action on mismatch:
new_failures = post_failing - set(with_patches)
if new_failures:
    # Your fix caused a new regression. Revert that patch hunk and restart
    # at Step 1 with the smaller patch — do NOT stack another cross-cutting
    # edit on top.
    raise SystemExit(f"regression introduced: {new_failures}")

if post_failing and all(verdict.get(t) in {"pre_existing",
                                           "pre_existing_latent"}
                        for t in post_failing):
    # Clean enough: remaining failures are the ones you proved pre-existing
    # (classic or latent-under-collection-error). Stop. Report. Do not emit
    # another patch — jump to "Finalize deliverables when green".
    print("stopping: only pre-existing / latent failures remain")
```

If `new_failures` fires, the next corrective action is **revert the last
patch hunk and shrink its scope** before anything else — not another patch
on top. If `post_failing` still contains tests you have NOT classified, go
back to Step 1 for those tests; do not escalate to shared-machinery edits
until each remaining failure has a recorded verdict. If the
`pre_existing_latent` assertion fires, delete the extra patch file(s) you
emitted beyond the collection-restoring one, re-run `<TEST_COMMAND>` to
confirm `failing_now` is exactly `{the latent test}`, and then finalize.
