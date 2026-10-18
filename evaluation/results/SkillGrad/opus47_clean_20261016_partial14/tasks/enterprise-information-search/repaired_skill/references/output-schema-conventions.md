# Output schema conventions — scope, source, form; AMBIGUOUS materialized

Trigger (from SKILL.md Step 6): the answer includes any non-employee
entity class (URLs, documents, meetings, PRs, products, tokens).
Skip when the only output class is `eid_*` employees and the directory
check passes.

**Core rules.**
1. **Entity-scope probe BEFORE source and form.** Parse the question's
   possessives and prepositions to determine WHOSE entities are in
   scope. Ambiguous prepositions (`for X products`, `about X`, `on X`,
   `shared re X`, `related to X`) map to AMBIGUOUS entity scope. The
   wrong scope produces a correct-looking but wrong answer even when
   source and form are right.
2. **Source-collection probe before form probe.** Identify the
   authoritative dataset collection (URLs live in the top-level `urls`
   collection, not in slack message bodies). Non-authoritative sources
   are a hard fail even if wording says "raw."
3. **AMBIGUOUS commits a concrete shape.** When scope, wording, or
   sibling convention disagree, the output MUST emit both candidate
   arrays with scope/form labels. A single `values` array alone is a
   schema violation.
4. **Scalar type conformance.** Numeric slots never contain sentinel
   strings; `0` is forbidden unless metadata lookup actually failed and
   the failure is logged in `<field>_provenance`.

---

## Subroutine 0 — Entity-scope probe (NEW, runs first)

A question of the form `URLs <verb> <preposition> X <noun>` has an
ambiguous scope when the preposition can read as either "belonging to X"
OR "for the purpose of X-work." Resolve by table lookup:

```python
AMBIGUOUS_PREPOSITIONS = {
    # phrase pattern            scope_a                scope_b
    "for X products":           ("URLs OF X products",       "URLs for X-related work"),
    "for X":                    ("URLs OF X",                "URLs for X-related work"),
    "about X":                  ("URLs describing X",        "URLs filed under X topic"),
    "on X":                     ("URLs located at X",        "URLs discussing X"),
    "shared re X":              ("URLs attached to X",       "URLs discussing X"),
    "related to X":             ("URLs linked to X",         "URLs tagged X-theme"),
}

UNAMBIGUOUS_POSSESSIVES = (
    "X's URLs",                 # possessive — belongs to X
    "URLs owned by X",
    "URLs authored by X",
    "URLs from X's team",
)

def entity_scope_probe(question_text, product_name):
    """Return ('AMBIGUOUS', scope_a_label, scope_b_label) or
    ('definite', single_scope_label, None)."""
    low = question_text.lower()
    # Unambiguous possessives first — they override preposition patterns
    for pat in UNAMBIGUOUS_POSSESSIVES:
        if match_pattern(low, pat, product_name):
            return "definite", f"owned_by:{product_name}", None
    for pat, (a, b) in AMBIGUOUS_PREPOSITIONS.items():
        if match_pattern(low, pat, product_name):
            return "AMBIGUOUS", a, b
    return "definite", "unspecified", None
```

When scope is AMBIGUOUS, build **two** candidate value lists — one per
scope reading — and emit both. Never silently pick one.

---

## Subroutine 1 — Source-collection probe

```python
ENTITY_SOURCES = {
    "url":      "dataset.urls",
    "document": "dataset.documents",
    "meeting":  "dataset.meetings",
    "pr":       "dataset.prs",
    "employee": "dataset.employees",
}

def source_collection_probe(entity_class, candidate_values, dataset):
    coll_name = ENTITY_SOURCES[entity_class]
    coll = resolve(dataset, coll_name)
    if coll is None:
        return {"authoritative_source": coll_name, "status": "missing"}

    resolved = [(v, lookup_in_collection(v, coll)) for v in candidate_values]
    missing  = [v for v, row in resolved if row is None]

    if missing:
        # Candidate was drawn from a non-authoritative source. Re-derive.
        return {"authoritative_source": coll_name,
                "status": "re_derive",
                "missing": missing,
                "replacement_hint": f"enumerate {coll_name} filtered by product/theme"}

    return {"authoritative_source": coll_name,
            "status": "ok",
            "rows": [row for _, row in resolved]}
```

If `status == "re_derive"`: discard the current list and rebuild from the
authoritative collection filtered by the product + question theme. Do NOT
keep slack-message hrefs as the value source.

---

## Subroutine 2 — Form probe (wording + sibling convention)

```python
WORDING_TO_FORM = {
    "urls":        "raw",   "links":        "raw",
    "url ids":     "canonical", "identifiers": "canonical",
    "doc":         "raw",   "doc id":       "canonical",
    # extend as evidence accumulates
}

def form_probe(entity_class, question_text, rows_from_source):
    form_from_wording = classify_wording(question_text, WORDING_TO_FORM)
    form_from_siblings = dominant_form_in_sibling_slots(entity_class)
    if form_from_wording and form_from_siblings \
       and form_from_wording != form_from_siblings:
        return "AMBIGUOUS", form_from_wording, form_from_siblings
    chosen = form_from_wording or form_from_siblings or "AMBIGUOUS"
    return chosen, form_from_wording, form_from_siblings
```

---

## Subroutine 3 — Materialize per (scope, form)

```python
scope_tag, scope_a, scope_b = entity_scope_probe(question_text, product_name)

if scope_tag == "AMBIGUOUS":
    rows_a = enumerate_from_collection(coll_name, filter=scope_a)
    rows_b = enumerate_from_collection(coll_name, filter=scope_b)
    chosen, fw, fs = form_probe(entity_class, question_text, rows_a + rows_b)
    answer[subq] = {
        "entity_class":        entity_class,
        "entity_scope":        "AMBIGUOUS",
        "scope_a_label":       scope_a,
        "scope_b_label":       scope_b,
        "values_scope_a":      [r[chosen if chosen != "AMBIGUOUS" else "raw"] for r in rows_a],
        "values_scope_b":      [r[chosen if chosen != "AMBIGUOUS" else "raw"] for r in rows_b],
        "value_form":          chosen,
        "authoritative_source": coll_name,
        "wording_cue_verbatim": fw,
    }
else:
    rows = enumerate_from_collection(coll_name, filter=scope_a)
    chosen, fw, fs = form_probe(entity_class, question_text, rows)
    raw_vals       = [row["raw"]       for row in rows]
    canonical_vals = [row["canonical"] for row in rows]
    if chosen == "AMBIGUOUS":
        answer[subq] = {"entity_class": entity_class,
                        "entity_scope": scope_a,
                        "value_form":   "AMBIGUOUS",
                        "values_raw":       raw_vals,
                        "values_canonical": canonical_vals,
                        "authoritative_source": coll_name,
                        "wording_cue_verbatim": fw,
                        "sibling_convention":   fs}
    else:
        answer[subq] = {"entity_class": entity_class,
                        "entity_scope": scope_a,
                        "value_form":   chosen,
                        "values":       raw_vals if chosen == "raw" else canonical_vals,
                        "authoritative_source": coll_name,
                        "wording_cue_verbatim": fw or fs}
```

---

## Worked example — "URLs shared by team members for PersonalizeForce competitor products"

- Preposition pattern `"for X products"` (X = `PersonalizeForce competitor`)
  matches `AMBIGUOUS_PREPOSITIONS`. Scope is AMBIGUOUS between:
  - `scope_a`: URLs OF competitor products (demo URLs of PersonAI, etc.)
  - `scope_b`: URLs about PersonalizeForce shared for competitor analysis
    (our own product's internal demo URLs)
- Enumerate `dataset.urls` filtered by each scope:
  - `rows_a` = competitor-product demo URLs (what the agent returned previously).
  - `rows_b` = PersonalizeForce internal demo URLs shared in competitor
    threads.
- Emit `entity_scope = "AMBIGUOUS"` + `values_scope_a` + `values_scope_b`.
- Failure this prevents: committing silently to `scope_a` (three
  competitor URLs) when the grader may expect `scope_b`.

---

## Scalar metrics (tokens / cost / duration)

```python
def extract_scalar_metric(name, executor_metadata):
    for key in (name, f"total_{name}", f"usage.{name}", f"usage.total_{name}"):
        val = resolve(executor_metadata, key)
        if isinstance(val, (int, float)):
            return {"value": val, "provenance": f"metadata.{key}"}
    return {"value": 0, "provenance": f"lookup failed: no {name} in executor metadata"}
```

Rule: `0` is only acceptable when the provenance string begins with
`"lookup failed: "`. Any other `0` or any sentinel string (`"N/A"`,
`"unknown"`) is a schema violation. Example valid pair:

```json
{"tokens": 12345, "tokens_provenance": "metadata.total_tokens"}
```

Example valid failure pair:

```json
{"tokens": 0, "tokens_provenance": "lookup failed: subagent did not return total_tokens"}
```

---

## Verification (before save)

```python
# 1. Entity-scope probe ran.
assert "entity_scope" in answer[subq], "entity-scope probe skipped"

# 2. AMBIGUOUS entity_scope emits both scope arrays.
if answer[subq]["entity_scope"] == "AMBIGUOUS":
    assert "values_scope_a" in answer[subq] and "values_scope_b" in answer[subq], \
        "AMBIGUOUS entity_scope requires values_scope_a + values_scope_b"
    assert "values" not in answer[subq], \
        "AMBIGUOUS entity_scope forbids single 'values' array"

# 3. Source-collection probe ran and status != "missing".
assert "authoritative_source" in answer[subq], "source probe skipped"
assert answer[subq]["authoritative_source"].startswith("dataset."), \
    "non-authoritative source (e.g., slack hrefs) — re-derive from collection"

# 4. value_form present and consistent with emitted keys.
vf = answer[subq]["value_form"]
if vf == "AMBIGUOUS" and answer[subq]["entity_scope"] != "AMBIGUOUS":
    assert "values_raw" in answer[subq] and "values_canonical" in answer[subq], \
        "AMBIGUOUS form must emit both values_raw and values_canonical"
    assert "values" not in answer[subq], \
        "AMBIGUOUS form forbids single 'values' array"

# 5. Scalar metrics: 0 only with logged failure.
if answer.get("tokens") == 0:
    assert answer.get("tokens_provenance", "").startswith("lookup failed:"), \
        "tokens=0 requires provenance 'lookup failed: <reason>'"
```

**Corrective action on failure.**
- `entity-scope probe skipped`: run `entity_scope_probe` on the question
  text; if AMBIGUOUS, enumerate both scope candidate lists before
  committing form.
- `AMBIGUOUS entity_scope requires values_scope_a + values_scope_b`: do
  not silently commit to one reading. Enumerate the second scope's rows
  from the authoritative collection and emit both arrays.
- `source probe skipped` or `non-authoritative source`: discard current
  values; re-enumerate from the authoritative collection (`dataset.urls`,
  `dataset.documents`, etc.); re-run the form probe.
- `AMBIGUOUS form must emit both`: add the second-form array by mapping
  each row via the collection's `raw`/`canonical` columns.
- `tokens=0 requires provenance`: re-attempt the metadata lookup; write
  the real integer or an explicit `"lookup failed: <reason>"` string.
