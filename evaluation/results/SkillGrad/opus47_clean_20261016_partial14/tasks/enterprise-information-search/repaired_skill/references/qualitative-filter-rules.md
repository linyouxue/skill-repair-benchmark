# Qualitative-filter rules — structural first, hard wording table, cardinality-checked

Trigger (from SKILL.md Step 0.5): the question asks for people who
`provided / gave / offered / contributed / discussed` something qualitative
(insights, feedback, strengths, weaknesses, competitor analysis, concerns)
sourced from slack threads, meeting transcripts, or free-text comments.
Skip when inclusion is pinned by a structural field alone (e.g.,
`document.reviewers`, `pr.assignees`).

**Core rules.**
1. **Structural signals before slack filtering.** The baseline inclusion
   set comes from `documents[*].feedback` and `meeting_transcripts.*`
   entries on the qualitative theme, NOT from slack keyword grep.
2. **Strict trichotomy, no middle bucket.** Narrow = top-level originators
   only. Broad = every poster in the relevant threads (URL-only +
   ack-only + clarifying-question-only + context-discussants ALL
   included). AMBIGUOUS = both arrays emitted with cardinalities.
   A judgment-built middle set (e.g., "substantive contributors" with
   URL-only culled but clarifying-only kept) is a schema violation.
3. **Wording-cue table is a HARD LOOKUP, not a soft hint.** The width is
   derived mechanically from the question's verbatim phrases via the
   table in Subroutine 2. Verbal reasoning about "what the agent thought
   the wording meant" cannot override the table.
4. **Pre-commit cardinality sanity check.** The emitted answer size must
   equal either the narrow candidate's size or the broad candidate's size
   exactly. Any size strictly between the two triggers AMBIGUOUS
   re-emission with both arrays.

---

## Subroutine 1 — Structural-signal probe (must run first)

```python
def structural_signal_probe(doc_ids, qualitative_theme):
    """Return the baseline inclusion set from structural fields, BEFORE
    any slack thread is read."""
    S = set()
    sources = {"documents.feedback": [], "meeting_transcripts": []}

    for d in doc_ids:
        for version in find_all_versions(d):
            for bullet in version.get("feedback", []) or []:
                authors = extract_feedback_authors(bullet)
                if theme_matches(bullet, qualitative_theme):
                    S.update(authors)
                    sources["documents.feedback"].append(
                        {"doc": d, "version": version.id,
                         "authors": sorted(authors)})

    for mt in find_meeting_transcripts_on_theme(doc_ids, qualitative_theme):
        speakers = speakers_on_theme(mt, qualitative_theme)
        S.update(speakers)
        sources["meeting_transcripts"].append(
            {"meeting": mt.id, "speakers": sorted(speakers)})

    return sorted(S), sources
```

If `S` is non-empty, it is the baseline. Any slack-derived expansion must
be surfaced as a **separate candidate rule** in the plan, not merged into
the primary set.

---

## Subroutine 2 — HARD wording-cue lookup table

The table maps verbatim phrases from the question text to a width. If the
exact phrase (or a listed near-synonym) appears in the question, that
width wins. If neither column matches, width is AMBIGUOUS — do not pick
by vibes.

```python
NARROW_CUES = [
    # Phrasings that explicitly denote filtered subsets
    "key reviewers",       "key insights",        "key feedback",
    "primary contributors","main contributors",
    "substantive feedback","substantive contributors",
    "authored feedback",   "gave feedback",       "provided feedback",
    "provided insights",   "insights on strengths","insights on weaknesses",
    "insights on strengths/weaknesses",
    "described strengths", "described weaknesses",
    "explained strengths", "explained weaknesses",
]

BROAD_CUES = [
    "members who discussed",  "team members involved",
    "everyone who posted",    "everyone who replied",
    "anyone who posted",      "all contributors",
    "all participants",       "anyone in the thread",
]

def classify_width(question_text):
    low = question_text.lower()
    hit_narrow = next((c for c in NARROW_CUES if c in low), None)
    hit_broad  = next((c for c in BROAD_CUES  if c in low), None)
    if hit_narrow and not hit_broad: return "narrow",    hit_narrow
    if hit_broad  and not hit_narrow: return "broad",     hit_broad
    return "AMBIGUOUS", None   # includes both-match and neither-match
```

**Table maintenance.** When a new wording appears in a question and is not
in either column, do not guess — classify as AMBIGUOUS and add the phrase
to the appropriate column after the task is resolved.

---

## Subroutine 3 — Build both candidate sets regardless of the pick

```python
def build_candidate_sets(threads, structural_S):
    # Narrow: structural S ∪ top-level originators of thematic claims.
    narrow = set(structural_S) | {t.author for t in threads
                                  if t.is_top_level and t.originates_claim}
    # Broad: every poster in the relevant threads, no judgment exclusions.
    broad  = set(structural_S) | {m.author for t in threads for m in t.messages}
    return sorted(narrow), sorted(broad)
```

Edge-case posters that MUST be in `broad` (never culled by judgment):
URL-only, ack-only (`"Thanks!"`, `"Agreed!"`, 👍-only, "Sounds good"),
clarifying-question-only, context-discussant.

---

## Subroutine 4 — Emit the plan with cardinality sanity check

```python
width, cue = classify_width(question_text)
structural_S, structural_sources = structural_signal_probe(doc_ids, theme)
narrow, broad = build_candidate_sets(threads, structural_S)

plan = {
    "entity_class": "employee_eid",
    "qualitative_theme": theme,
    "structural_baseline": structural_S,
    "structural_sources":  structural_sources,
    "inclusion_width":     width,
    "wording_cue_verbatim": cue,
    "candidate_narrow":    narrow,
    "candidate_broad":     broad,
    "cardinality": {"narrow": len(narrow), "broad": len(broad)},
}

if width == "narrow":
    plan["values"] = narrow
elif width == "broad":
    plan["values"] = broad
else:  # AMBIGUOUS
    plan["values_narrow"] = narrow
    plan["values_broad"]  = broad
```

### Cardinality sanity check (runs after the pick)

```python
def cardinality_sanity_check(plan):
    n_narrow = plan["cardinality"]["narrow"]
    n_broad  = plan["cardinality"]["broad"]
    if "values" in plan:
        size = len(plan["values"])
        if size != n_narrow and size != n_broad:
            raise AssertionError(
                f"middle-bucket size {size} (narrow={n_narrow}, broad={n_broad}) "
                "— re-emit as AMBIGUOUS with both arrays")
    # UNION-ALL detector: a 'narrow' answer that equals the broad set is suspect
    if plan.get("inclusion_width") == "narrow" \
       and len(plan.get("values", [])) == n_broad and n_narrow < n_broad:
        raise AssertionError(
            "width=narrow but values=broad set — wording cue says narrow, "
            "answer is broad; re-emit with candidate_narrow")
```

---

## Worked example — six competitor threads, "provided insights on strengths/weaknesses"

- Threads span 16 unique posters total. `candidate_broad` has 16 eids
  (includes ack-only `"Thanks!"`, `"Agreed!"`, 👍-only replies).
- Top-level originators of strength/weakness claims across the six
  threads: `eid_5318af37, eid_fce6544f, eid_c9c3d8d5, eid_d2f0f99a,
  eid_a253c65a` (5 eids). `candidate_narrow` has 5 eids.
- Verbatim phrase in question: `"provided insights on
  strengths/weaknesses"` → matches `NARROW_CUES` entry
  `"insights on strengths/weaknesses"`. ⇒ width = `narrow`, cue =
  `"insights on strengths/weaknesses"`.
- Emit `plan["values"] = narrow` (5 eids). Cardinality check passes
  (`5 == n_narrow`).
- Failure mode this prevents: emitting the 16-poster union against a
  narrow wording cue. `cardinality_sanity_check` would reject the
  16-eid answer because `width == "narrow"` but `size == n_broad`.

---

## Verification (before save)

```python
# 1. Structural probe ran and recorded sources (even if empty).
assert "structural_sources" in plan, "structural probe skipped"
assert set(plan["structural_sources"].keys()) >= \
       {"documents.feedback", "meeting_transcripts"}, \
       "structural probe did not cover both sources"

# 2. Width was derived from the hard table.
assert plan["inclusion_width"] in ("narrow", "broad", "AMBIGUOUS"), \
       "width must come from classify_width"
if plan["inclusion_width"] != "AMBIGUOUS":
    assert plan["wording_cue_verbatim"] is not None, \
        "narrow/broad requires a verbatim cue from NARROW_CUES or BROAD_CUES"

# 3. Cardinality sanity.
cardinality_sanity_check(plan)

# 4. AMBIGUOUS materialization.
if plan["inclusion_width"] == "AMBIGUOUS":
    assert "values_narrow" in plan and "values_broad" in plan, \
        "AMBIGUOUS requires both arrays"
    assert "values" not in plan, "AMBIGUOUS forbids single 'values' array"
```

**Corrective action on failure.**
- `structural probe skipped`: run the probe NOW; do not proceed with a
  slack-only candidate list.
- `narrow/broad requires a verbatim cue`: either the cue is in the table
  and `classify_width` missed it (add the phrase and re-run) or there is
  no cue (re-classify as AMBIGUOUS and emit both arrays).
- `middle-bucket size`: discard the hand-built set. Re-emit as
  `values_narrow` + `values_broad` with `inclusion_width = "AMBIGUOUS"`,
  OR set values exactly equal to `candidate_narrow` or `candidate_broad`
  with the matching cue cited.
- `width=narrow but values=broad set`: pull `candidate_narrow` and emit
  it. The UNION-ALL default fired; the wording cue requires a filtered
  subset.
