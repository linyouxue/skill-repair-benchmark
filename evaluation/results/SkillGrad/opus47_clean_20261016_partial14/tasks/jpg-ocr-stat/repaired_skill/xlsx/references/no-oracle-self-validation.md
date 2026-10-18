# Stop condition when no external oracle is available

**When to read this chapter.** The task has noisy inputs (OCR, scraped
HTML, parsed PDFs, screenshots) and no accessible oracle — no held-out
labels, no reference parser, no structured source to cross-check
against. You must decide when to stop iterating on the extractor
without being able to score your output against a known-correct answer.
Skip when the task provides any external verifier (schema validator
with semantic rules, a second parser, canonical source data, golden
examples in the problem statement).

**Core problem.** Lacking an oracle, the natural shortcut is to open a
few raw inputs, eyeball what the answers "should be", type them into a
dict (`expected = {"071.jpg": ("2018-02-19", "17.70"), ...}`) inside a
debug script, and iterate the extractor until
`pipeline_output == expected`. This **silently selects for
self-consistent-but-wrong pipelines**: the stop condition is your own
guess, so the extractor is trained to your eyeball labels instead of
to reality, and the real oracle's disagreements are invisible to you.
The output looks perfectly shaped (right columns, right row count,
right types, every row populated) and reward is still 0.0.

The failure is structural, not fixable by looking harder — looking
harder is exactly what produced the self-authored table in the first
place.

---

## 1. The forbidden pattern — self-authored `expected` as stop condition

If your debug/test code contains any of these shapes, delete them
before saving:

```python
# FORBIDDEN — self-authored ground truth
expected = {
    "071.jpg": ("2018-02-19", "17.70"),   # eyeballed from OCR dump
    "039.jpg": ("2018-03-30", "35.00"),   # picked from mode-vote
    # ... 20 more rows ...
}
for item_id, actual in pipeline_output.items():
    assert actual == expected[item_id], f"{item_id}: {actual} != {expected[item_id]}"
```

```python
# FORBIDDEN — same anti-pattern, softer phrasing
wrong = [i for i, v in pipeline_output.items() if v != my_guess[i]]
print(f"{len(wrong)} rows still disagree with my table; tuning...")
```

The anti-pattern is **not** "I inspected a few inputs" — it is "I
used my inspection as the pass/fail stop condition for extractor
tuning". The two look identical on the first iteration and diverge
on the fifth, when the extractor has been bent to match your guesses
on the ambiguous rows.

Runtime branch:
- **The debug script contains a hard-coded `expected`/`gold`/`truth`
  dict covering most/all input ids** → delete it, replace with the
  intrinsic signals in §2.
- **The debug script contains an `expected` dict covering only a
  handful of unambiguous cases (sanity anchors)** → keep, but do NOT
  use it as the all-rows stop condition; only as a smoke test on
  rows where the answer is beyond doubt.

**Verification check — what to do on mismatch.** Grep your workspace
for `expected = {`, `gold = {`, `truth = {`, `ground_truth = {` in
`.py` files written this session. If any match has more than ~3
entries covering the ambiguous rows:
- **Next corrective action**: remove the dict, re-run with the §2
  intrinsic signals as the stop condition, and allow some rows to
  ship as low-confidence (§3) rather than tuned-to-match-your-guess.

---

## 2. Intrinsic consistency signals — the legitimate stop condition

Intrinsic signals do not depend on your eyeball labels. Use them in
combination; no single one is sufficient.

```python
def intrinsic_score(row, siblings, cross_variant_votes, validators):
    """Return a per-row health report — not a boolean pass/fail."""
    report = {}

    # (a) Validator pass — every typed field satisfies its predicate.
    report["validators"] = {f: v(row.get(f)) for f, v in validators.items()}

    # (b) Cross-field reconciliation — sibling fields constrain target.
    #     Receipt: cash - change ≈ total.  Invoice: subtotal + tax = grand.
    report["reconcile"] = reconcile_siblings(row, siblings)

    # (c) Cross-variant numeric agreement — > 1 variant produced the
    #     same numeric value for this field (not just same tier).
    report["variant_agreement"] = {
        f: cross_variant_votes.get(f, {}).get(row.get(f), 0)
        for f in validators
    }

    # (d) Distributional sanity — row's values fall in the plausible
    #     window the full batch defines.
    report["in_distribution"] = {
        "date_year": 2000 <= parse_year(row.get("date")) <= 2099,
        "amount_positive": (row.get("amount") or 0) > 0,
        "amount_bounded": (row.get("amount") or 0) < 10_000,
    }

    return report
```

Runtime branch:
- **All four signals pass for a row** → row is HIGH-CONFIDENCE; ship.
- **One or more signals weak or missing (e.g. no sibling to reconcile
  against)** → row is MEDIUM-CONFIDENCE; ship the current best
  candidate but do not iterate further on it unless signals improve.
- **Signals conflict (reconcile fails, OR two variants tied with
  different numeric values, OR validator-false)** → row is
  LOW-CONFIDENCE; see §3.

**Verification check — what to do on mismatch.** After one full-batch
run, count HIGH / MEDIUM / LOW. If more than ~20% of rows are LOW:
- **Next corrective action**: this is a signal that the extractor
  rules are miscalibrated across the batch, not that the batch has
  hard rows. Revisit the extraction rule (keyword patterns, exclusion
  aliases, PSM sweep) rather than tuning per-row — a global rule
  change is cheaper and better-generalising than per-row patches.

---

## 3. Low-confidence rows ship as-is — do not tune to a guess

A LOW-confidence row has two legitimate dispositions. The illegitimate
third option — "pick what my eye says and tune the extractor until it
matches" — is the exact pattern §1 forbids.

```python
def disposition(row_id, report, raw_input):
    """Decide what to do with one LOW-confidence row."""
    # Legitimate option A: ship the pipeline's current best candidate.
    #   The real oracle (unknown to us) gets to discover the disagreement.
    #   Our guess cannot help here — it is at best as reliable as the
    #   pipeline's own vote and at worst biased by what we hope the
    #   answer is.
    if not raw_input_is_cheap_to_inspect(raw_input):
        return ("ship_pipeline_pick", row.get_best())

    # Legitimate option B: inspect ALL low-confidence rows for this
    #   batch (not a convenient subset) and record uncertainty
    #   explicitly. If you inspect, you commit to inspecting all of
    #   them with the same procedure, and you record your inspection
    #   choice separately (e.g. in a sidecar notes file) rather than
    #   folding it back into the extractor as training data.
    if committed_to_inspect_all_low_confidence:
        human_pick = read_raw_and_record(row_id, raw_input)
        log_uncertainty(row_id, human_pick, confidence="eyeball_only")
        return ("ship_human_pick", human_pick)

    # FORBIDDEN hybrid: eyeball a subset, tune the extractor until
    # that subset matches, declare success. This is §1's anti-pattern.
    raise RuntimeError("hybrid eyeball+tune is forbidden")
```

Runtime branch:
- **Row count small (<10) and inspection is cheap** → option B is
  defensible; commit to all-rows inspection.
- **Row count moderate/large OR inspection is expensive OR the inputs
  are genuinely ambiguous** → option A: ship the pipeline pick. The
  oracle will tell you which specific rows disagreed; your eyeball
  will not.

**Verification check — what to do on mismatch.** Before saving the
workbook, grep your own notes/trace for the forbidden hybrid tells:
`"X still disagrees with my table"`, `"tuning until matches expected"`,
`"my expected says Y but pipeline says Z"`. If any appear:
- **Next corrective action**: revert the per-row tuning changes made
  after the self-authored table was introduced, re-run the pipeline
  with the pre-tuning rules, and ship those outputs; the tuned-to-
  match version is biased toward your guesses and strictly worse in
  expectation on the hidden oracle.

---

## 4. OCR-variant ties → flag, do not pick

Mode voting and "prefer v0" are tie-breakers, not validators. When
two OCR variants return different values for the SAME field with
equal (or near-equal) frequency — e.g. `30/03/2018` vs `30/05/2018`
on an ambiguous month digit, or `538.00` vs `598.00` on a smudged
hundreds digit — the row is **ambiguous by any intrinsic measure**.
Picking one and declaring the row matched is a self-authored-oracle
move in miniature.

```python
def resolve_variant_tie(field_votes, cross_field_sibling=None):
    """field_votes: dict[value → variant_count]. Returns (value, confidence)."""
    if not field_votes:
        return (None, "no_candidate")
    sorted_votes = sorted(field_votes.items(), key=lambda kv: -kv[1])
    top_value, top_count = sorted_votes[0]
    runner_up_count = sorted_votes[1][1] if len(sorted_votes) > 1 else 0

    # Clear majority → high confidence.
    if top_count >= 2 * runner_up_count and top_count >= 2:
        return (top_value, "majority")

    # Tie or near-tie → consult sibling constraints before picking.
    if cross_field_sibling is not None:
        reconciling = [v for v, _ in sorted_votes
                       if reconciles_with(v, cross_field_sibling)]
        if len(reconciling) == 1:
            return (reconciling[0], "tie_broken_by_reconcile")

    # Still tied → flag as ambiguous. Ship the top-vote value but
    # record it as low-confidence; do NOT iterate on this row to
    # bend the vote toward a guess.
    return (top_value, "ambiguous_shipped_as_low_confidence")
```

Runtime branch:
- **Clear majority (top ≥ 2× runner-up and top ≥ 2 variants)** →
  accept the majority.
- **Near-tie but one candidate reconciles with sibling fields** →
  pick the reconciling candidate.
- **Near-tie with no reconciler** → ship top-vote as low-confidence
  and move on. Do NOT: add more PSM modes just for this row until
  the vote tips in your preferred direction; do NOT: switch to a
  different preprocessing recipe only because it produces the
  answer you expected.

**Verification check — what to do on mismatch.** After the full
batch, list every row whose status is `ambiguous_shipped_as_low_
confidence`. If the list is non-empty:
- **Next corrective action**: this is EXPECTED and legitimate — do
  NOT iterate further on these rows unless you find a global rule
  improvement (e.g. a new preprocessing variant that resolves ties
  across many rows, not just the ones where you guessed the
  answer). Record the list in a sidecar `low_confidence.txt` and
  ship the workbook.
