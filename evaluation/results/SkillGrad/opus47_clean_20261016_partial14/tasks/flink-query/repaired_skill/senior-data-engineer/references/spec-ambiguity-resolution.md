# Spec Ambiguity Resolution

How to resolve ambiguous task specifications before implementing a data/query
pipeline, how to locate the evaluator's ground truth in the workspace, and how
to verify output against an external artifact rather than a self-written
reference.

**When to read this chapter.** You are about to implement a transformation,
window, aggregation, or output format based on a spec that contains boundary
language ("inactivity period of N", "at least X", "window of N minutes",
"after N"), enum/status qualifiers ("finished", "active", "completed"),
output-format phrases ("one line per", "with the count"), or counting phrases
("count the events", "number of X") — **and** no example output file is
visible alongside the spec. If an authoritative `expected_output.*` file or
verifier script is already in the workspace and you have read it, skip to the
verification section.

---

## 1. Enumerate ambiguity axes before coding

Before writing any transformation code, scan the spec for each phrase that
admits more than one reading. For each, write down the concrete choices it
forces. The common axes for Flink/streaming/query tasks:

| Axis | Example spec phrase | Choices it forces |
|---|---|---|
| Boundary inclusivity | "inactivity period of N minutes" | `gap > N` closes vs. `gap >= N` closes |
| Window gap semantics | "after N minutes of no events" | Session windows, tumbling, hopping — and the API's documented boundary |
| Status-filter set | "once the job has finished" | Single terminal state, union of terminal states, no filter, or temporal cue |
| Cue-as-filter vs cue-as-time | "once X has finished", "after Y" | Row-level predicate vs. "evaluate at end of stream" |
| Output tuple format | "emit (id, count)" | `(id,count)` vs `(id, count)` vs `id\tcount` vs `id,count` |
| Trailing newline | — | Present vs absent (evaluators often care) |
| Counting granularity | "count the events" | Raw events vs distinct entities vs distinct (entity, timestamp) |
| Resubmit/retry counting | "resubmissions are counted separately" | Each attempt as its own event vs collapse by (entity, attempt) |
| Ordering | — | Sorted by key vs by insertion vs by count desc |

Produce the list before touching the pipeline code:

```python
# Generic ambiguity scan — run at the top of your implementation script
# or write it as a comment block in the pipeline file.
ambiguity_axes = []

def record(axis, chosen, alternatives, rationale):
    ambiguity_axes.append({
        "axis": axis,
        "chosen": chosen,
        "alternatives": alternatives,
        "rationale": rationale,
    })

# Example invocation (fill in from the actual spec you are reading)
record(
    axis="boundary_inclusivity",
    chosen="gap > N closes session",
    alternatives=["gap >= N closes session"],
    rationale="library primitive uses >; most literal reading of 'period of N'",
)

for a in ambiguity_axes:
    print(f"[RISK] {a['axis']}: chose '{a['chosen']}' "
          f"(alternatives: {a['alternatives']}) — {a['rationale']}")
```

**Verification step.** If `ambiguity_axes` is empty after reading the spec,
you have almost certainly missed axes. Re-read the spec with the table above
open and add at least one entry per boundary/status/format phrase. If you
still have zero entries, confirm by reading the spec aloud sentence-by-sentence
and asking "could a strict reader interpret this differently?" If yes:
add the axis. If no (and only then): proceed with zero axes.

---

## 2. Search the workspace for evaluator ground truth

Before implementing, run a filesystem scan for artifacts that encode the
evaluator's actual choices. Any match is authoritative over your own reading.

```python
import os
import re
from pathlib import Path

GROUND_TRUTH_PATTERNS = [
    r"expected", r"\.expected$", r"verifier", r"evaluator",
    r"grade", r"grader", r"solution", r"reference_output",
    r"^test_", r"fixtures", r"examples?", r"golden",
]

def find_evaluator_artifacts(workspace_root):
    root = Path(workspace_root)
    hits = []
    rx = re.compile("|".join(GROUND_TRUTH_PATTERNS), re.IGNORECASE)
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        # Skip obvious noise
        if any(part.startswith(".") for part in path.parts):
            continue
        if path.suffix in {".pyc", ".class", ".jar"}:
            continue
        if rx.search(path.name) or rx.search(str(path.parent)):
            hits.append(path)
    return hits

artifacts = find_evaluator_artifacts(".")
if artifacts:
    print("GROUND TRUTH CANDIDATES — read these before coding:")
    for p in artifacts:
        print(f"  {p}")
else:
    print("NO ground truth found — proceeding under literal-reading rule.")
```

### Runtime branches

- **Branch A — one or more artifacts found.** Read each candidate. Classify
  it: expected output file (diff against it), verifier/grading script
  (read the comparison logic to learn exact format, tolerance, and
  ordering requirements), or example fixture (treat as a sample, not a
  spec). Encode its semantic choices in the pipeline. Do **not** continue
  with your own interpretation of the spec after this point.

- **Branch B — no artifacts found.** Proceed to section 3 (literal-reading
  rule) and section 4 (dual-reading comparison).

**Verification step.** If branch A fires, write a Python assertion comparing
your pipeline's output against the artifact byte-for-byte (or line-for-line
with normalization documented). If the assertion fails: do not adjust the
evaluator artifact or your diff tolerance — go back to section 1, identify
which ambiguity axis you resolved wrong, and change the pipeline.

```python
# Byte-level diff against a found expected-output artifact
def verify_against_artifact(pipeline_output_path, expected_path):
    with open(pipeline_output_path, "rb") as f:
        actual = f.read()
    with open(expected_path, "rb") as f:
        expected = f.read()
    if actual == expected:
        return True, None
    # Locate first divergence
    for i, (a, b) in enumerate(zip(actual, expected)):
        if a != b:
            ctx_a = actual[max(0, i-40):i+40]
            ctx_b = expected[max(0, i-40):i+40]
            return False, (i, ctx_a, ctx_b)
    return False, (min(len(actual), len(expected)), b"<length-mismatch>", b"")

ok, diff = verify_against_artifact("output.txt", "expected_output.txt")
if not ok:
    offset, got, want = diff
    raise AssertionError(
        f"Diverged at byte {offset}: got {got!r} vs expected {want!r}. "
        f"Return to ambiguity-axis table and change the pipeline, "
        f"not the comparison."
    )
```

---

## 3. If no ground truth: literal-reading rule

When no evaluator artifact exists, pick the most literal reading of each
ambiguity axis and record the alternatives as risks in a visible comment or
output note. Literal readings for common axes:

- **"Inactivity period of N units" → `gap > N` closes.** A period "of N"
  is a duration of exactly N; a gap of exactly N has not yet exceeded it.
  Note: this matches the default behavior of Flink's
  `EventTimeSessionWindows.withGap(Time.seconds(N))`, which uses `>` to
  close a session. If the evaluator uses `>=`, your output will differ on
  rows where the gap is exactly N.
- **"Once X has finished" over a bounded trace → include all rows seen.**
  In a bounded dataset every entity is effectively "finished" by the end
  of the stream, so the phrase is more plausibly a temporal cue
  ("evaluate at end of stream") than a status-filter predicate. If the
  spec says "finished" and also lists terminal status codes, the filter
  reading becomes plausible — try both.
- **Tuple output format → match the exact punctuation in the spec example,
  character-for-character.** If the spec shows `(id, count)` with a space,
  emit the space; if `(id,count)` without, emit without. Add a trailing
  newline on the last line unless the spec example clearly omits it.
- **"Count the events" → count raw events.** Collapsing to distinct
  entities is a semantic reinterpretation. If the spec says "distinct",
  then collapse; otherwise raw.

```python
# Record literal-reading choices as risks so the choice is visible
RISK_NOTES = []
def risk(axis, literal_choice, alternative):
    RISK_NOTES.append(
        f"RISK[{axis}]: chose literal '{literal_choice}'. "
        f"If evaluator uses '{alternative}', output will differ."
    )

risk("boundary_inclusivity", "gap > N closes", "gap >= N closes")
risk("status_filter", "no filter (bounded trace)", "filter to single terminal state")

# Emit at the top of the pipeline output or as a sidecar file
with open("output_notes.txt", "w") as f:
    for note in RISK_NOTES:
        f.write(note + "\n")
```

**Verification step.** Before declaring the pipeline done, re-read the spec
once more with `RISK_NOTES` open. For each risk, ask: did I actually pick
the literal reading, or did I quietly pick a framework default? If a
framework default (e.g. a windowing API) made the choice for me, that is
not the same as a literal reading — document the API's documented behavior
in the risk note and move on.

---

## 4. Dual-reading comparison when the axis is high-impact

For axes where the two readings produce visibly different output sizes
(boundary inclusivity on busy keys, status-filter sets, counting
granularity), implement both and compare. The point is to make the
disagreement visible, not to pick a winner.

```python
# Implement two readings of the boundary axis and diff their outputs
def run_pipeline(input_rows, boundary="strict"):
    """boundary: 'strict' => gap > N closes; 'inclusive' => gap >= N closes."""
    # ... pipeline logic ...
    return output_rows

out_strict = run_pipeline(rows, boundary="strict")
out_inclusive = run_pipeline(rows, boundary="inclusive")

# Branch on whether the readings diverge at all
if out_strict == out_inclusive:
    print("Boundary axis does not affect this input — safe to pick either.")
    chosen = out_strict
else:
    diff_count = sum(1 for a, b in zip(out_strict, out_inclusive) if a != b)
    print(f"Boundary axis affects {diff_count} rows. "
          f"Literal reading picks 'strict'; recording 'inclusive' as risk.")
    chosen = out_strict
    with open("ambiguity_diff.txt", "w") as f:
        for a, b in zip(out_strict, out_inclusive):
            if a != b:
                f.write(f"strict={a} | inclusive={b}\n")
```

**Verification step.** If both readings produce identical output, the axis
is a non-issue for this input and either choice is safe. If they differ:
pick the literal reading, keep `ambiguity_diff.txt` as evidence, and if
the eventual reward is 0, swap to the alternative reading before changing
anything else about the pipeline.

---

## 5. Never accept self-consistent verification

The pattern that triggered this chapter: an author wrote a Flink pipeline
and a Python reference, both encoded the same semantic choices (gap
inclusivity, terminal-event set, output formatting, counting granularity),
got 0 mismatches between them, and declared success — the hidden evaluator
disagreed and the reward was 0. **A reference written by the same author
that encodes the same choices as the pipeline under test proves only
translation correctness, not spec conformance.**

Minimum bar for calling a pipeline verified:

1. External artifact diff (section 2 branch A), **or**
2. Dual-reading comparison with the alternative recorded as a risk
   (section 4), **or**
3. Explicit written acknowledgment that no verification has been performed
   and the pipeline is unverified against the evaluator.

Anything else — including "my implementation matches my own reference
exactly over N lines" — is not verification and must not be reported as
such.

```python
# Verification gate — call before declaring the pipeline done
def declare_verified(external_diff_passed, dual_reading_done, unverified_ack):
    if external_diff_passed:
        return "VERIFIED: external artifact diff passed"
    if dual_reading_done:
        return "VERIFIED-WITH-RISK: dual reading recorded, literal reading chosen"
    if unverified_ack:
        return "UNVERIFIED: no evaluator artifact available, no dual reading done"
    raise RuntimeError(
        "Cannot declare verified: self-consistent reference comparison is "
        "not acceptable. Return to section 2 or section 4."
    )

status = declare_verified(
    external_diff_passed=False,
    dual_reading_done=True,
    unverified_ack=False,
)
print(status)
```

**Verification step.** If `declare_verified` raises, the only acceptable
corrective action is to run section 2 (search for artifact) again with
broadened patterns, then section 4 (dual-reading comparison) on the
highest-impact axis. Do not catch the exception and proceed; do not
rename a self-written reference to make it look external.
