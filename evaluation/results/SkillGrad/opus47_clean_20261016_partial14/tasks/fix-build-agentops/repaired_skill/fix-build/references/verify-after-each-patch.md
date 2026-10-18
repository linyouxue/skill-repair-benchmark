# Verifying the test suite after every patch

Read this after each `<TEST_COMMAND>` re-run during the Patch–rerun loop.
It converts the raw test output into a three-outcome decision: **stop**,
**continue**, or **revert** — plus two guard branches (**flake, not
regression** for noisy suites, and **shape = collection_error** for the
first run after a collection-restoring patch) that prevent a correct fix
from being reverted on bad evidence.

The branched algorithm uses two sets and one shape:

- `failing_prev` — the failing-test ids from the previous run (or, on the
  first re-run, the baseline set `failing_baseline` captured in SKILL.md
  "Define success before patching").
- `failing_now` — the failing-test ids from the run you just finished.
- `shape` — `collection_error` or `test_failures`, captured at baseline.

## Step 1 — Parse the failing-test ids from this run

```python
import re, subprocess

TEST_CMD = ["<TEST_COMMAND>"]  # from SKILL.md "Define success before patching"
proc = subprocess.run(TEST_CMD, capture_output=True, text=True)
output = proc.stdout + proc.stderr

# pytest marks every failing test with a line starting FAILED or ERROR
# followed by the test node id (path::Class::test_name).
failing_now = {
    m.group(1)
    for m in re.finditer(r"^(?:FAILED|ERROR)\s+(\S+)", output, re.MULTILINE)
}
exit_code = proc.returncode
print(f"exit={exit_code}, failing_now={sorted(failing_now)}")
```

If `exit_code == 0` the parser should return an empty set; if it does not,
the parser missed something (e.g. an xdist crash). Re-run with `-v` and
re-parse before trusting the branch below.

## Step 2 — Branch on the delta

```python
# failing_prev is carried over from the previous iteration;
# on the very first re-run it is the baseline set captured before any patch.
new_failures = failing_now - failing_prev
disappeared  = failing_prev - failing_now

if not failing_now:
    verdict = "stop_green"
elif new_failures and shape == "collection_error" and \
        failing_prev == failing_baseline:
    # First run after the collection-restoring patch. The baseline suite was
    # unreachable, so EVERY failing test is "new" under naive set-difference
    # even though none of these failures regressed anything that previously
    # passed. Do NOT jump to flake-check or revert — run the scope-match
    # check from SKILL.md.
    verdict = "continue_scope_match_check"
elif new_failures:
    verdict = "revert_last_patch"      # tentative — confirm in Step 2a
elif failing_now <= failing_prev:
    verdict = "continue_progress"
else:
    verdict = "continue_progress"

print(verdict, "new:", new_failures, "fixed:", disappeared)
```

Act on `verdict`:

- **`stop_green`** → The suite is green. **Do not emit another patch**, and
  do not keep rerunning the suite to "be sure" — jump to SKILL.md's
  "Finalize deliverables when green" section and write
  `patch_{i}.diff` / `failed_reasons.txt` first. Common temptation
  shapes to resist: "this singleton skips `__init__` on repeat calls, I
  should reset state in the module-level `init()` too"; "let me rerun
  10 more times to confirm". Each extra rerun exposes you to a flake-
  driven revert of a correct fix. Cap further reruns at 3.
- **`continue_scope_match_check`** → For each test in `new_failures`, run
  the four-question scope-match check from SKILL.md: (1) in
  `failing_baseline`? (2) would the patch touch files beyond the
  collection-restoring one? (3) would it alter public-API semantics?
  (4) if (1=No) + (2=Yes) + (3=Yes), STOP. In that STOP case, do NOT
  emit `patch_{N+1}.diff`; keep only the collection-restoring patch,
  document the newly-visible failure in `failed_reasons.txt` as a
  pre-existing latent bug exposed by the collection fix, and jump to
  "Finalize deliverables when green". Only if a given test survives the
  check (plain local fix in the same file, no public-API semantics
  change) may you emit a focused patch for it. For the branched
  per-test algorithm, read `references/triage-remaining-failure.md`
  Branch E.
- **`revert_last_patch`** → At least one previously-passing test now
  fails. **Before reverting, run Step 2a** to confirm the failure is
  stable rather than a flake. Only after Step 2a confirms a stable
  regression do you run the revert commands:

  ```bash
  # If the patch was committed as a diff file you applied:
  git apply -R patch_N.diff && rm patch_N.diff
  # Or, for uncommitted edits:
  git checkout -- <files_touched_by_patch_N>
  <TEST_COMMAND>                      # re-run to confirm the revert cleared it
  ```

  Do NOT layer a compensating patch on top. The compensating edit almost
  always widens into the shared machinery the ceiling rule was trying to
  keep you out of.
- **`continue_progress`** → `failing_now` is a non-empty strict subset of
  `failing_prev`. Set `failing_prev = failing_now`, classify the remaining
  failures using SKILL.md's floor/ceiling/scope-match decision rule, and
  emit the next focused patch.

## Step 2a — Confirm flake vs regression before reverting

Triggered when Step 2 produced a tentative `revert_last_patch`. The
delta-rollback rule assumes `<TEST_COMMAND>` output is a deterministic
function of the patch stack. When the repo has test-isolation issues
(shared singleton state across tests, request-count assertions sensitive
to ordering, time-based assertions, background-thread races), the same
patch stack can produce different failing sets on consecutive runs — a
newly-failing test is then a **flake**, not a regression.

```python
# Re-run with NO edits; capture 2-3 more samples of the failing set.
reruns = []
for _ in range(2):   # 2 extra samples; add a third if the first two disagree
    r = subprocess.run(TEST_CMD, capture_output=True, text=True)
    reruns.append({
        m.group(1)
        for m in re.finditer(r"^(?:FAILED|ERROR)\s+(\S+)",
                             r.stdout + r.stderr, re.MULTILINE)
    })

# Branch A: at least one rerun shows the newly-failing test passing
#           → FLAKE on this patch stack. Do a clean-baseline comparison.
# Branch B: every rerun shows the same new failures as the first red run
#           → stable REGRESSION. Proceed to the revert commands in Step 2.
if any(new_failures - r for r in reruns):
    verdict = "flake_candidate"
else:
    verdict = "revert_last_patch"      # confirmed
```

If `verdict == "flake_candidate"`, confirm the flake is pre-existing (not
caused by your patches) with a clean HEAD-side baseline. The stash MUST
be clean — a partial stash invalidates the comparison:

```bash
git stash push -u -m "fix-build:baseline"
git status --porcelain       # MUST print nothing tracked; abort if it does
<TEST_COMMAND>; <TEST_COMMAND>; <TEST_COMMAND>   # same N reruns on HEAD
git stash pop
```

```python
# Verification step with corrective action on failure.
status = subprocess.run(["git", "status", "--porcelain"],
                        capture_output=True, text=True).stdout
if status.strip():
    # Stash was incomplete (common with untracked or ignored files).
    # Corrective action: reconcile the working tree before retrying.
    #   git stash pop                     # restore your patches
    #   git stash push -u --include-untracked -m "fix-build:baseline-2"
    #   git status --porcelain            # verify empty before continuing
    raise SystemExit("baseline not clean; comparison invalid, reconcile first")

# Compare flake rates on overlapping test ids.
head_flaky = {t for r in head_reruns for t in r}
if head_flaky & new_failures:
    verdict = "flake_not_regression"   # pre-existing flake, keep patches
else:
    verdict = "revert_last_patch"      # flake is yours, revert
```

Act on the final verdict:

- **`flake_not_regression`** → `git stash pop` to restore your patches
  and treat the suite as green. Jump to SKILL.md's "Finalize
  deliverables when green" immediately — do not run another 10+
  confirmation passes.
- **`revert_last_patch`** (confirmed) → Run the revert commands in
  Step 2.

## Step 3 — Verification before emitting the next patch

Before you write `patch_{N+1}.diff`, re-check the invariants:

```python
assert verdict in {"stop_green", "continue_progress",
                   "flake_not_regression",
                   "continue_scope_match_check"}, (
    "revert_last_patch means NO new patch — go revert first"
)
if verdict == "stop_green":
    assert exit_code == 0, "green verdict but non-zero exit — re-parse output"
    # Corrective action: do not emit patch_{N+1}; go write deliverables.
if verdict == "flake_not_regression":
    # Corrective action: do not emit patch_{N+1} either; go write
    # deliverables. Record the HEAD-side flake evidence in
    # failed_reasons.txt as "pre-existing test-isolation flake,
    # orthogonal to the fix".
    pass
if verdict == "continue_scope_match_check":
    # Corrective action: for each test in new_failures, apply the
    # four-question scope-match check. If any test fails the check
    # (not in failing_baseline + patch touches additional files + patch
    # alters public-API semantics), do NOT emit patch_{N+1} for it;
    # record it in failed_reasons.txt as pre-existing latent bug and
    # go write deliverables. Only emit a patch for a test that passes
    # the check (plain local fix in the same file, no API semantics
    # change).
    pass
if verdict == "continue_progress":
    assert failing_now < failing_prev_snapshot, (
        "continue requires a strict subset; otherwise you are stacking "
        "without evidence of progress"
    )
    # Corrective action on mismatch: go back to Step 2 and recompute;
    # if truly no progress, revert the last patch and pick a different fix.
```

Corrective actions summary:

- Assertion `verdict in {...}` fires → you are about to stack on top of a
  regression; go run the revert commands under `revert_last_patch` above
  before anything else.
- Assertion `exit_code == 0` fires → your parser disagrees with pytest;
  re-run `<TEST_COMMAND> -v` and re-parse before trusting any verdict.
- Assertion `failing_now < failing_prev_snapshot` fires → the last patch
  did not shrink the failing set. Revert it and pick a different fix at a
  narrower site; do not emit another patch on top of a no-op.
- `git status --porcelain` non-empty inside Step 2a → the stash is
  incomplete, the HEAD comparison is invalid; reconcile the working tree
  (restore patches, re-stash with `--include-untracked`, verify empty)
  before re-running the baseline. Do NOT revert based on an unclean
  baseline.
- `continue_scope_match_check` with a test that passes the check (plain
  local fix) → emit `patch_{N+1}.diff` as normal, but keep its blast
  radius minimal; each additional file touched beyond the baseline fix
  raises the probability of grader rejection and should be weighed
  against submitting the minimal fix as-is.
