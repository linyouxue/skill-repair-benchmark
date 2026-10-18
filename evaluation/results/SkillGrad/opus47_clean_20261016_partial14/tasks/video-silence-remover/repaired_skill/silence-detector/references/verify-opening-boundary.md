# Verify Opening Boundary

Use this procedure after every `detect_silence.py` invocation whose output
feeds a downstream cut (pause-detector `--start-time`, segment-combiner,
or video-processor). The detector returns well-formed JSON even when it
has over-trimmed, so a programmatic plausibility gate is required.

**There are exactly five sanctioned final boundary values: Branches
A/B/C/D/E below.** Any other value — a hand-picked timestamp, an
energy inflection, a round number, a visually-chosen frame, or a
re-run of the detector with different parameters to restore an earlier
value — is a forbidden shortcut (see end of this file). The 20% figure
in Check 1 is a *suspicion trigger* that dispatches to the branches,
not a hard cap on the final boundary.

## Calibration note (iter_4 falsified an earlier worked example)

The original check2 compared the detector's threshold against
`overall_mean`. On teaching videos with wide dynamic range (loud
explanation sections pull the mean up), a legitimate low-energy
opening boundary auto-failed check2 regardless of ground truth, and
the branch ladder deterministically routed to Branch C's 90 s cap —
which turned out to over-trim by ~70 s on a 601 s video where Branch
B's 18 s was closer to the truth.

Two miscalibrations drove this:

- **Mean is the wrong statistic for check2.** The baseline threshold
  should be judged against a *lower-tail* energy statistic (median
  or 25th percentile), because real quiet content later in the
  video is the right reference for "below this = silence", not the
  loud-sections-inflated mean.
- **Amplitude step is the wrong statistic for check3.** Pre-roll
  (room tone / mic setup) and the start of quiet speech can be at
  nearly identical RMS. The distinguishing feature is
  frequency/variance (speech varies second-to-second; noise does
  not), not amplitude.

Both checks have been rewritten below. The forbidden-shortcut list
is also narrower now: a short Branch B output whose check1 passes is
no longer automatically wrong just because check2/check3 fail under
the old amplitude-based rules.

## Worked numeric example (recalibrated checks)

Inputs: `total_seconds = 601`, task hint = none.

| Step | Action | Result | check1 | check2′ | check3′ |
|------|--------|--------|--------|---------|---------|
| 1 | Branch A (defaults) | opening_end = 221 s | FAIL (37%) | FAIL (thr vs low-tail baseline) | FAIL (no variance step) |
| 2 | Branch B (`--threshold-multiplier 1.15 --initial-window 20`) | opening_end = 18 s | pass (3%) | pass (thr=1125 ≥ 1.5 × low_floor if low_floor ≈ 500–800) | pass (speech variance > noise variance) |
| 3 | If check2′ and check3′ both pass on B → commit Branch B. If one still fails but check1 passes AND Branch B's opening is ≥5× shorter than Branch A's → **Branch B-wins override** commits B. Otherwise → Branch C. |

**Correct final answer in this situation: 18 s** (Branch B's retry
output). The earlier "90 s is correct" worked example was an
iter_3-grounded guess that iter_4 falsified; it has been removed.

Wrong answers and the shortcut each represents:

- `221 s` — revert-to-defaults. The default-parameter output is the
  value that failed every check at step 1; re-producing it is not a
  branch.
- `75 s` (or any other hand-picked energy inflection) — reject-and-invent.
  Not the output of any branch.
- `90 s` — stale worked-example cap. Only legal when Branch B's
  check1 fails or when Branch B's opening is <5× shorter than Branch A's
  *and* the recalibrated check2′/check3′ both fail on B.
- Hand-chosen frame-sampling timestamp — frame sampling is record-only
  (see Forbidden Shortcuts).

If the recalibrated checks still fail *and* Branch B does not meet the
override condition, Branch C's cap is next; its default ceiling has
been tightened (see Branch C).

## Required pre-write commitment (two lines, both mandatory)

Before writing any opening value into pause-detector / segment-combiner /
video-processor input, emit **both** of the following in the trace:

1. One of the five commitment strings naming the branch:
   - `"Branch A: accepting detector output of N seconds (all recalibrated checks pass)"`
   - `"Branch B: accepting retry output of N seconds (stricter params, recalibrated checks or large-shrink override)"`
   - `"Branch C: applying cap of M seconds = min(task_hint_or_30, int(0.05 * total))"`
   - `"Branch D: nudged boundary to N seconds (check3′ fix)"`
   - `"Branch E fallback: task cap of K seconds, mismatch recorded (B and C both failed)"`

2. A **consistency assertion** showing the committed branch's exit
   condition holds on the current check values. Template:

   ```
   Commitment <branch> requires <exit condition>; current values:
   check1=<True|False> check2'=<True|False> check3'=<True|False>
   large_shrink=<True|False>.
   ```

   Per-branch exit conditions (checks evaluated against the output
   that would be committed):

   | Branch | Exit condition that must hold on current values |
   |--------|--------------------------------------------------|
   | A | check1=True AND check2′=True AND check3′=True |
   | B | (check1=True AND check2′=True AND check3′=True) OR (check1=True AND large_shrink=True) |
   | C | Branch B has been run AND its output does not satisfy B's exit condition |
   | D | check1=True AND check2′=True AND (check3′ fixed by walk-forward) |
   | E | Branch B AND Branch C have both been run and still ≥1 check fails |

   If the assertion's exit condition is not satisfied by the current
   values, the commitment is **invalid**: do not write downstream
   input, enter the next sanctioned branch, re-run the full algorithm,
   and re-emit both lines.

Narrating observations and then picking a number without emitting both
lines is the exact shortcut this procedure is designed to prevent.

## Trigger

Run this procedure when any of:

- Detected opening duration is > ~15–20% of total video duration.
- Threshold sits within ~2× of overall mean energy.
- The task description gives qualitative hints about the opening
  ("static title card", "~30 s intro", "short pre-roll").
- Downstream output must stay within an expected removed-duration range.

Skip when the task is a short clip (< 60 s) or when the detector returns
an empty `segments` list (no opening to trim).

## Full verification algorithm (recalibrated)

```python
import json
import numpy as np

silence = json.load(open("silence.json"))
energies = json.load(open("energies.json"))

total_seconds = energies["total_seconds"]
energy_values = np.array(energies["energies"], dtype=float)
overall_mean = float(energies["stats"]["mean"])

segments = silence["segments"]
opening_end = segments[0]["end"] if segments else 0
opening_dur = segments[0]["duration"] if segments else 0

initial_window = silence["parameters"]["initial_window"]
multiplier = silence["parameters"]["threshold_multiplier"]
baseline = float(energy_values[:initial_window].mean())
threshold = baseline * multiplier

# --- Check 1: opening fraction of total (suspicion trigger) ---
MAX_OPENING_FRACTION = 0.20   # suspicion threshold, NOT a final cap
frac = opening_dur / total_seconds if total_seconds else 0
check1_ok = frac <= MAX_OPENING_FRACTION

# --- Check 2' (recalibrated): threshold vs lower-tail energy, not mean ---
# Rationale: on wide-dynamic-range content, overall_mean is inflated by
# loud sections; the right reference for "silence" is the quiet floor.
low_floor = float(np.percentile(energy_values, 25))
check2_ok = threshold >= 1.5 * low_floor

# --- Check 3' (recalibrated): variance change OR amplitude step ---
# Rationale: noise→speech transitions have small amplitude change but
# large variance change. Accept either signal at the boundary.
def window_slice(start, end):
    s, e = max(0, start), min(len(energy_values), end)
    return energy_values[s:e]

before_win = window_slice(opening_end - 10, opening_end)
after_win  = window_slice(opening_end, opening_end + 10)

before_mean = float(before_win.mean()) if len(before_win) else 0.0
after_mean  = float(after_win.mean())  if len(after_win)  else 0.0
before_std  = float(before_win.std())  if len(before_win) else 0.0
after_std   = float(after_win.std())   if len(after_win)  else 0.0

amp_step_ok = (before_mean <= 1.5 * baseline) and (after_mean >= threshold)
var_step_ok = (before_std > 0) and (after_std >= 1.5 * before_std)
check3_ok = amp_step_ok or var_step_ok

# --- Large-shrink flag (used by Branch B's override exit condition) ---
# Only meaningful on the Branch B retry; set once Branch A's opening
# is known.
# large_shrink = (branch_A_opening_end / branch_B_opening_end) >= 5.0

print(f"opening={opening_dur}s ({frac:.1%} of {total_seconds}s)")
print(f"baseline={baseline:.1f}  threshold={threshold:.1f}")
print(f"overall_mean={overall_mean:.1f}  low_floor(p25)={low_floor:.1f}")
print(f"before_mean={before_mean:.1f}  after_mean={after_mean:.1f}")
print(f"before_std={before_std:.1f}    after_std={after_std:.1f}")
print(f"amp_step_ok={amp_step_ok} var_step_ok={var_step_ok}")
print(f"check1={check1_ok} check2'={check2_ok} check3'={check3_ok}")
```

## Runtime branches

Choose exactly one branch and emit the matching pre-write commitment
plus consistency assertion before writing any downstream input. The
branches are numbered; **you may not skip a branch** (Branch C
requires Branch B first; Branch E requires both B and C first).

### Branch A — all three (recalibrated) checks pass → accept.
Commit: `"Branch A: accepting detector output of N seconds (all recalibrated checks pass)"`.
Pass `opening_end` to pause-detector `--start-time`.

### Branch B — check1 fails OR check2′ fails → retry with stricter parameters.

**Exit condition (read this first): Branch B commits as final when
EITHER (a) check1=True AND check2′=True AND check3′=True on the retry
output, OR (b) the Branch-B-wins override holds: check1=True AND
Branch B's opening is ≥5× shorter than Branch A's opening (large
shrink under stricter params is strong evidence that Branch A's
baseline window was contaminated).**

Action: re-run with stricter params:

```bash
python3 /root/.claude/skills/silence-detector/scripts/detect_silence.py \
    --energies energies.json \
    --threshold-multiplier 1.15 \
    --initial-window 20 \
    --output silence.json
```

Then re-run the full recalibrated algorithm. Three outcomes:

- All three recalibrated checks pass on the retry → commit
  `"Branch B: accepting retry output of N seconds (stricter params, recalibrated checks or large-shrink override)"`
  with consistency assertion naming the matching exit condition. Use
  that boundary.
- Branch-B-wins override holds (check1=True AND
  `branch_A_opening / branch_B_opening >= 5`) → commit the same
  Branch B string with consistency assertion naming the override
  clause. The override exists because on wide-dynamic-range content
  (teaching videos, lectures) a legitimately placed quiet-to-quiet
  boundary can fail the amplitude-based parts of check3′ even after
  recalibration — but a 5×+ shrink under stricter params almost
  certainly reflects the real opening.
- Neither clause holds → **go to Branch C**. Do not commit Branch B.
  Do not re-run `detect_silence.py` with default parameters (see
  Forbidden Shortcuts).

#### Sub-note: which value feeds Branch C/E

When Branch B's retry produces a shorter opening than Branch A's,
Branch C/E uses the Branch B value when they need to reference the
"detector's best estimate" (e.g., for logging or report context).
Branch C's own output is still its own cap formula, independent of
B's number; Branch E's own output is still the task cap.

### Branch C — Branch B's retry does not meet B's exit condition OR task gives a hard qualitative hint ("~30 s intro") → cap and move on.

**Exit condition: Branch C is entered only after Branch B has been
attempted and its exit condition failed (both the all-checks-pass
clause and the large-shrink override). Branch C commits once its cap
value has been written to `silence.json`; a post-cap re-check
determines whether to escalate to Branch E.**

Set `opening_end` to the smaller of (a) the task-specified cap and
(b) `int(0.05 * total_seconds)`. If the task gives no numeric cap,
use `30` as the default ceiling (down from an earlier 90 s default,
which iter_4 showed was ~3× too generous for teaching videos).
Rewrite `silence.json` in place:

```python
cap = min(task_hint_or_30, int(0.05 * total_seconds))
silence["segments"] = [{"start": 0, "end": cap, "duration": cap}]
silence["total_duration_seconds"] = cap
json.dump(silence, open("silence.json", "w"))
```

Commit: `"Branch C: applying cap of M seconds = min(task_hint_or_30, int(0.05 * total))"`
plus consistency assertion ("Branch B was run; it did not meet
its exit condition; cap = M").

Then re-run the three recalibrated checks on the new capped opening.
If any still fail → **Branch E**. If all pass → Branch C's cap is
the final value.

### Branch D — check3′ fails only → nudge boundary.

**Exit condition: check1 was already True and check2′ was already
True before entering D; only check3′ is being repaired.** Walk
forward from `opening_end` one second at a time until a 5-second
window exceeds `threshold` OR shows ≥1.5× variance versus the
pre-boundary window; use that index as the corrected boundary.
Update `silence.json` as in Branch C. Commit:
`"Branch D: nudged boundary to N seconds (check3′ fix)"` plus
consistency assertion.

If check1 or check2′ is False, Branch D is not applicable; go to
Branch B.

### Branch E — Branches B and C have both been applied and the three checks still fail → task-cap fallback with recorded mismatch.

**Exit condition: both Branch B and Branch C have been run, and
Branch C's post-cap re-check still has ≥1 failing check.** The
opening is undetectable from energy alone. Fall back to the
task-specified cap verbatim; if the task gives no cap, use `0`
(remove no opening) rather than any larger guessed value. Rewrite
`silence.json` to that value, record the unresolved mismatch in the
final report (which checks failed, what Branches B and C produced,
what cap was applied), and proceed. Commit:
`"Branch E fallback: task cap of K seconds, mismatch recorded (B and C both failed)"`
plus consistency assertion.

Branch E's cap is the only sanctioned response to persistent failure.
Do not revert to the original detector output, do not re-run with
default parameters, do not substitute a hand-picked or
visually-chosen timestamp.

## Verification step (post-correction)

After applying any branch other than A, re-run the three recalibrated
checks on the updated `silence.json`, then dispatch:

```python
# Re-load corrected silence.json and recompute check1, check2', check3'.
# Then:
#   Branch B retry: if B's exit condition holds (all pass OR large-shrink
#                   override) → commit B. Otherwise → go to C.
#   Branch C cap:   if all three pass → commit C. If any False → go to E.
#   Branch D nudge: check1, check2', check3' must all pass; if not →
#                   treat as check1/check2' failure and go to Branch B.
#   Branch E:       checks may still fail — expected. Record mismatch
#                   in report, use the cap, do not escalate further.
```

Next corrective action by failure mode:

- Branch B retry fails exit condition → **Branch C** (not a defaults
  re-run, not a hand-picked timestamp).
- Branch C's post-cap recheck fails → **Branch E** (not a hand-picked
  value, not a revert to A).
- Branch E's cap feels "too short" visually → still use Branch E.
  Record the frame observation in the report; do not increase the
  cap.

## Forbidden shortcuts

These shortcuts have each produced task failures at this anchor and
are explicitly out of scope. If you find yourself about to do one,
stop and apply the next sanctioned branch instead.

- **Re-running `detect_silence.py` with default parameters after
  Branch B produced a shorter boundary.** This is a reversion, not a
  branch. The default-parameter output is exactly the value that
  failed Checks 1/2/3 at the start; re-producing it does not
  revalidate it. The sanctioned successor to a Branch B that fails
  its exit condition is Branch C's cap, then Branch E's fallback —
  never a defaults re-run.
- **Picking the earliest sharp energy drop** (e.g., 2270 → 311) as
  the boundary. Within a pre-roll, several such drops occur (music
  fade, scene cut, logo end) before real content starts; the first
  drop almost always lands *inside* the opening.
- **Hand-picking a round number** (60, 75, 90) that is not the output
  of Branch C's `min(task_hint_or_30, 0.05 * total)` formula or
  Branch E's task-cap fallback. Note: 90 was the Branch C default
  in an earlier iteration and is NOT the current default — if you
  are tempted toward 90 because an earlier worked example cited it,
  that example has been retracted.
- **Treating Check 1's 20% as a hard cap** on the final value and
  truncating `opening_end` to `0.20 * total_seconds` without first
  running Branch B.
- **Using frame sampling as an authorizing branch.** Frame sampling
  is a *record-only sanity step*. If used, sample at `opening_end`,
  `0.5 × opening_end`, and `1.5 × opening_end`, record what each
  frame contains, and include the observations verbatim in the
  report. Frame sampling CANNOT override Branch B/C/D/E numeric
  output, CANNOT authorize reverting to an earlier detector run, and
  CANNOT be used to pick a new boundary.
- **Subjective "lecture hasn't started yet" judgments.** Observations
  like "lecturer walking across the room", "still crowd / setup",
  "title card still showing", "teaching content hasn't visually
  begun" are NOT grounds to override a numeric branch output. The
  branches target *low-energy pre-roll removal*, not *the
  pedagogical start of the lecture*. Branch B's shorter boundary is
  correct for the task even if the lecturer is visually still
  setting up — the setup footage is content for this skill's
  purposes, because its audio energy exceeds threshold.
- **Narrating observations instead of committing to a branch.**
  Writing a paragraph about what frames show, what energies look
  like, or what the "right" answer feels like, and then writing a
  number into pause-detector input without naming which branch
  produced it, is the shortcut this entire procedure prevents. The
  two-line pre-write commitment (branch string + consistency
  assertion) is mandatory.
- **Rejecting Branch B's short output purely because check2/check3
  (uncalibrated or recalibrated) still fail, when its opening is
  ≥5× shorter than Branch A's.** The large-shrink override exists
  precisely for this case; iter_4 showed that forcing escalation to
  Branch C's cap in this regime over-trims the opening. If
  check1=True on B AND large_shrink=True, commit B.
```
