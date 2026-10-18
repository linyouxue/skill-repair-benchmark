# Literal-wording + schema audit — mechanically checkable, pre-save

Trigger (from SKILL.md Step 7): the task has ≥2 sub-questions, OR any
sub-question names a role, OR any top-level answer field has a declared
scalar type. Skip only when a single sub-question has no named roles and
no scalar metric fields.

**Core rules.**
1. **Required per-sub-question output keys** make each audit mechanically
   checkable — not a soft prose checklist.
2. **AMBIGUOUS materialization** — the audit refuses to pass when
   AMBIGUOUS is claimed but only one form/width/scope is emitted.
3. **Structural-source cross-reference** — each sub-question's evidence
   map must cite the structural source(s) checked AND record whether
   slack-derived candidates agree with the structural source.
4. **UNION-ALL default detector** — a sub-question whose final answer
   equals the full gathered-candidate union AND whose wording contains a
   narrowing cue is a hard schema violation. The agent must either
   re-derive the narrow candidate OR emit AMBIGUOUS with both arrays.

---

## Required output keys (per sub-question)

```python
REQUIRED_KEYS = {
    "value_form",              # "raw" | "canonical" | "AMBIGUOUS"
    "authoritative_source",    # named field or collection
    "wording_cue_verbatim",    # exact phrase from question, or null
    "evidence_sources_checked",# dict: {source_name: hits_list_or_empty}
}

ROLE_OR_ENTITY_CLASS_EXTRA = {
    "inclusion_width",         # "narrow" | "broad" | "AMBIGUOUS"
}

ROLE_EXTRACTION_EXTRA = {
    "tier_used",               # "tier_1_union" | "tier_1_union_per_loop" | ...
    # plus per-role arrays, one per role named in the question
}

SCALAR_METRIC_EXTRA = {
    "tokens_provenance",       # "metadata.total_tokens" | "lookup failed: <reason>"
}
```

Any missing required key = schema violation = block save.

---

## UNION-ALL detector

Narrowing-cue phrases that imply a filtered subset answer:

```python
NARROWING_CUES = (
    "key", "primary", "main", "substantive",
    "provided insights", "gave feedback", "authored", "key reviewers",
    "described", "explained",
)

def union_all_detector(subq, q_text):
    """Return True if this sub-question looks like a UNION-ALL default
    against a wording that requires filtering."""
    low = q_text.lower()
    cue_hits = [c for c in NARROWING_CUES if c in low]
    if not cue_hits:
        return False
    final = _flatten_values(subq)
    gathered = _flatten_values(subq.get("evidence_sources_checked", {}))
    if not gathered:
        return False
    ratio = len(set(final)) / max(1, len(set(gathered)))
    # ratio ≈ 1.0 → final answer unions essentially every gathered candidate
    return ratio >= 0.95 and len(set(final)) >= 2

def _flatten_values(obj):
    """Collect all eid_*/id-like strings in nested lists/dicts."""
    out = []
    if isinstance(obj, dict):
        for v in obj.values(): out.extend(_flatten_values(v))
    elif isinstance(obj, list):
        for v in obj: out.extend(_flatten_values(v))
    elif isinstance(obj, str):
        out.append(obj)
    return out
```

A positive detector result means the executor silently defaulted to
UNION-ALL across sources even though the wording cue requires filtering.
The audit rejects this and the executor must choose:
- (a) re-run `qualitative-filter-rules.md`'s narrow derivation (or
  `tier-1-reviewer-sweep.md`'s scoped union for a target version) and
  re-emit the filtered set, OR
- (b) materialize AMBIGUOUS with both narrow and broad arrays
  (`values_narrow` + `values_broad`, or
  `key_reviewer_candidates_per_loop`).

---

## Branched audit

```python
def audit(answer, questions, schema):
    failures = []

    for subq_key, subq in answer.items():
        if not is_subquestion(subq_key):
            continue
        q_text = questions[subq_key]

        # Branch 1: required keys present
        missing = REQUIRED_KEYS - subq.keys()
        if missing:
            failures.append((subq_key, f"missing keys: {missing}"))

        # Branch 1b: role-or-entity-class extra keys
        if parse_named_roles(q_text) or subq.get("entity_class") in \
                ("url", "document", "meeting", "pr"):
            missing = ROLE_OR_ENTITY_CLASS_EXTRA - subq.keys()
            if missing:
                failures.append((subq_key,
                    f"inclusion_width required: {missing}"))

        # Branch 2: role-extraction extras
        roles = parse_named_roles(q_text)
        if roles:
            missing = ROLE_EXTRACTION_EXTRA - subq.keys()
            if missing:
                failures.append((subq_key, f"role-extraction missing: {missing}"))
            for r in roles:
                arr_key = f"{r}_employee_ids"
                if arr_key not in subq and \
                   "key_reviewer_candidates_per_loop" not in subq:
                    failures.append((subq_key, f"role array missing: {arr_key}"))
            if any("_and_" in k and k.endswith("_ids") for k in subq):
                failures.append((subq_key, "merged role list detected"))

        # Branch 3: AMBIGUOUS materialization (width, form, scope)
        iw = subq.get("inclusion_width")
        vf = subq.get("value_form")
        es = subq.get("entity_scope")
        if iw == "AMBIGUOUS":
            if "values_narrow" not in subq or "values_broad" not in subq:
                if "key_reviewer_candidates_per_loop" not in subq:
                    failures.append((subq_key,
                        "AMBIGUOUS width requires both narrow/broad arrays "
                        "or per-loop candidates"))
            if "values" in subq:
                failures.append((subq_key,
                    "AMBIGUOUS width forbids single 'values' array"))
        if vf == "AMBIGUOUS":
            if ("values_raw" not in subq or "values_canonical" not in subq) \
               and es != "AMBIGUOUS":
                failures.append((subq_key,
                    "AMBIGUOUS form requires values_raw + values_canonical"))
        if es == "AMBIGUOUS":
            if "values_scope_a" not in subq or "values_scope_b" not in subq:
                failures.append((subq_key,
                    "AMBIGUOUS entity_scope requires values_scope_a + values_scope_b"))

        # Branch 4: structural-source cross-reference
        esc = subq.get("evidence_sources_checked", {})
        structural_expected = structural_sources_for(q_text)
        unchecked = [s for s in structural_expected if s not in esc]
        if unchecked:
            failures.append((subq_key,
                f"structural sources not checked: {unchecked}"))

        slack_set = set(esc.get("slack_threads", []))
        struct_set = set(sum((esc.get(s, []) for s in structural_expected), []))
        if slack_set and struct_set and slack_set != struct_set:
            if vf != "AMBIGUOUS" and iw != "AMBIGUOUS":
                failures.append((subq_key,
                    "slack-derived candidates disagree with structural source "
                    "and neither inclusion_width nor value_form is AMBIGUOUS"))

        # Branch 5: UNION-ALL default against a narrowing cue
        if union_all_detector(subq, q_text) and iw not in ("AMBIGUOUS",):
            failures.append((subq_key,
                "UNION-ALL default against narrowing cue — "
                "re-derive narrow set or emit inclusion_width=AMBIGUOUS"))

    # Branch 6: scalar type conformance (top-level)
    if "tokens" in answer:
        if not isinstance(answer["tokens"], int):
            failures.append(("tokens", "non-integer"))
        if answer["tokens"] == 0 and \
           not answer.get("tokens_provenance", "").startswith("lookup failed:"):
            failures.append(("tokens", "0 without logged failure"))

    return failures
```

---

## Verification

```python
failures = audit(answer, questions, schema)
assert not failures, f"audit failed: {failures}"
write_answer_json(answer)
```

**Corrective action on each failure class.**
- `missing keys: {...}`: fill the keys from the plan built in Step 0.5 /
  Step 6. If the plan has no value for a key, the plan itself is
  incomplete — re-run the matching step before saving.
- `inclusion_width required`: classify via the hard wording-cue table in
  `qualitative-filter-rules.md` (or by target-version in
  `tier-1-reviewer-sweep.md`); emit `inclusion_width` + matching arrays.
- `role array missing`: split the merged list using the role-separation
  rule in `tier-1-reviewer-sweep.md`; emit one array per role named in
  the question. If version is silent, emit
  `key_reviewer_candidates_per_loop` with per-loop cardinalities.
- `AMBIGUOUS requires both forms/widths/scopes`: pull the second array
  from the plan's `candidate_narrow` / `candidate_broad` /
  `values_scope_a` / `values_scope_b` or from the authoritative source
  collection; emit both; remove any single `values` array.
- `structural sources not checked`: return to Step 5 (reviewer sweep) or
  Step 0.5 (qualitative filter) and run the structural probe for the
  missing source; record hits (possibly empty) in
  `evidence_sources_checked`.
- `slack-derived candidates disagree`: mark the sub-question AMBIGUOUS
  and emit both candidate sets, OR explain the disagreement in evidence
  (e.g., slack candidates failed product grounding) and re-run the audit.
- `UNION-ALL default against narrowing cue`: run
  `qualitative-filter-rules.md`'s `candidate_narrow` derivation and
  re-emit; OR for role-extraction, run
  `tier-1-reviewer-sweep.md`'s `scoped_union(target_version)`; if
  version/width is genuinely silent, emit AMBIGUOUS with both arrays.
- `tokens 0 without logged failure`: re-attempt the metadata lookup;
  write the real integer or a provenance string beginning with
  `"lookup failed: "`.
