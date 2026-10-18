---
name: enterprise-artifact-search
description: Multi-hop evidence search + structured extraction over enterprise artifact datasets (docs/chats/meetings/PRs/URLs). Strong disambiguation to prevent cross-product leakage; returns JSON-ready entities plus evidence pointers.
---

# Enterprise Artifact Search Skill (Robust)

This skill delegates **multi-hop artifact retrieval + structured entity extraction** to a lightweight subagent, keeping the main agent’s context lean.

It is designed for datasets where a workspace contains many interlinked artifacts (documents, chat logs, meeting transcripts, PRs, URLs) plus reference metadata (employee/customer directories).

Key upgrades layered on top of the basic retrieval loop:
1) **Signal enumeration + explicit inclusion/exclusion rules** (prevents extraction-on-first-pass; forces falsifiable predicates per sub-question).
2) **Product grounding & anti-distractor filtering** (prevents mixing one product's artifacts with another's).
3) **Tier-1 reviewer extraction, version-scoped, with role separation** (prevents “meeting participants == reviewers”, cross-loop merging, and multi-role flattening).
4) **Entity-scope + source + form probes for non-employee outputs** (prevents whose-entity ambiguity, non-authoritative source values, and silent form oscillation).
5) **Literal-wording + schema-type audit with UNION-ALL detector before save** (prevents silent reinterpretation, UNION-ALL defaults against narrowing cues, and scalar-type violations).

---

## When to Invoke This Skill

Invoke when ANY of the following is true:

1. The question requires **multi-hop** evidence gathering (artifact → references → other artifacts).
2. The answer must be **retrieved** from artifacts (IDs/names/dates/roles), not inferred.
3. Evidence is scattered across multiple artifact types (docs + slack + meetings + PRs + URLs).
4. You need **precise pointers** (doc_id/message_id/meeting_id/pr_id) to justify outputs.
5. You must keep context lean and avoid loading large files into context.

---

## Invocation

Use this format:

```python
Task(subagent_type="enterprise-artifact-search", prompt="""
Dataset root: /root/DATA
Question: <paste the question verbatim>

Output requirements:
- Return JSON-ready extracted entities (employee IDs, doc IDs, URL IDs, etc.).
- Provide evidence pointers: artifact_id(s) + short supporting snippets.

Constraints:
- Avoid oracle/label fields (ground_truth, gold answers).
- Prefer primary artifacts (docs/chat/meetings/PRs/URLs) over metadata-only shortcuts.
- MUST enforce product grounding: only accept artifacts proven to be about the target product.
- MUST state explicit inclusion AND exclusion rules per sub-question before extracting any ID.
- MUST match answer value form to the question's literal wording cross-checked against sibling-answer convention.
- MUST emit `inclusion_width` (narrow/broad/AMBIGUOUS) on every role or entity-class sub-question.
""")
```

---

## Core Procedure (Must Follow)

### Step 0 — Parse intent + target product
- Extract:
  - target product name
  - entity types needed per sub-question (author IDs, reviewer IDs, URL IDs, …)
  - artifact types likely relevant (reports, docs, review threads)
  - **target version** when the question names one (`"final"`, `"latest"`,
    `"draft"`, a date). Record it; Step 5's version-scope filter depends
    on it.

If product name is missing in question, infer cautiously from nearby context ONLY if explicitly supported by artifacts; otherwise mark AMBIGUOUS.

---

### Step 0.5 — Decompose question, enumerate signals, state inclusion rule

For each qualitative sub-question (people who `provided / gave / discussed /
contributed` something), inclusion comes from a **structural signal probe
first** (`documents[*].feedback` on every version +
`meeting_transcripts.*` on the theme), with slack filtering only as a
secondary candidate rule. Widths resolve to one of three states — pick
**mechanically** from the hard wording-cue table (narrow phrases like
`"key"`, `"primary"`, `"provided insights"`; broad phrases like
`"everyone who posted"`; otherwise AMBIGUOUS). Hand-built middle buckets
are forbidden; the final answer size must equal either the narrow
candidate size or the broad candidate size exactly.

```python
plan[subq] = {
    "entity_class":          "<entity>",
    "structural_baseline":   [...],         # from documents.feedback + meetings
    "candidate_narrow":      [...],
    "candidate_broad":       [...],
    "inclusion_width":       "narrow | broad | AMBIGUOUS",
    "wording_cue_verbatim":  "<exact phrase from question, or null>",
    "authoritative_source":  "documents.feedback | meeting_transcripts | ...",
    "cardinality":           {"narrow": len(narrow), "broad": len(broad)},
}
```

Decision rule: if `inclusion_width == "AMBIGUOUS"`, emit both
`values_narrow` and `values_broad` with cardinalities. If
`inclusion_width == "narrow"` or `"broad"`, the emitted `values` size
must equal that candidate's size exactly — any middle size triggers
AMBIGUOUS re-emission.

Read `references/qualitative-filter-rules.md` when the question asks for
people who `provided / gave / offered / contributed / discussed` something
qualitative. Skip when inclusion is pinned by a structural field alone
(e.g., `document.reviewers`, `pr.assignees`).

---

### Step 1 — Build candidate set (wide recall, then filter)
Search in this order:
1) Product artifact file(s): `/root/DATA/products/<Product>.json` if exists.
2) Global sweep (if needed): other product files and docs that mention the product name.
3) Within found channels/meetings: follow doc links (e.g., `/archives/docs/<doc_id>`), referenced meeting chats, PR mentions.

Collect all candidates matching the artifact type the question targets.

---

### Step 2 — HARD Product Grounding (Anti-distractor gate)
A candidate artifact is **VALID** only if it passes **at least 2 independent grounding signals**:

A) Located under the correct product artifact container (e.g., inside `products/<Product>.json` *and* associated with that product’s planning channels/meetings).
B) Document content/title explicitly mentions the target product name or a canonical alias list you derive from artifacts.
C) Shared in a channel whose name is clearly for the target product (e.g., `planning-<Product>`, `#<product>-*`) OR a product-specific meeting series.
D) The document id/link path contains a product-specific identifier consistent with the target product (not another product).
E) A meeting transcript discussing the artifact includes the target product context in the meeting title/series/channel reference.

**Reject rule:** if the artifact content repeatedly names a different product and lacks target-product grounding → DISTRACTOR, discard.

---

### Step 3 — Select the correct artifact version
If multiple VALID artifacts exist, choose by precedence:

1) Explicit “latest” marker
2) Explicit “final” marker
3) Most recent `date` field
4) Most frequently referenced in follow-up discussions

Keep the selected artifact’s id/link as the anchor. When later steps need
author or reviewer evidence, iterate over **every** version — do not
collapse to "latest" silently.

---

### Step 4 — Extract author(s), reconciling across versions

Extract authors in priority order:
1) Document fields: `author`, `authors`, `created_by`, `owner`
2) PR fields if introduced via PR: `author`, `created_by`
3) Slack: the user who posted “Here is the …” message (only if clearly linked and product-grounded)

**When the document has multiple versions, extract authors from EVERY
version** and emit the union when they diverge. Defaulting to the "latest"
version's author silently is a recurring failure mode.

Normalize to `eid_*` via the employee directory when only a name appears.

---

### Step 5 — Extract key reviewers (Tier-1 scoped UNION across sources)

Key reviewers are **evidence-based contributors**, not attendees. The
Tier-1 set is the **UNION** across every populated Tier-1 source — but
union only within a review loop that terminates **at or before the
question's target version**. A cross-loop union (e.g., merging
post-publication meeting attendees into a pre-publication reviewer set)
is wrong even when every individual source is Tier-1. Sources include
`document.reviewers`, `key_reviewers`, `approvers`, `requested_reviewers`,
`document.feedback` on EVERY version, share-message slack threads on
EVERY share event, `meeting_transcripts.*` speaker-attributed review
quotes, and `prs.reviews`. Participation (meeting attendance, ack-only
replies) is not review.

**Role separation is mandatory.** When a question names ≥2 roles, emit
one array per role; a flat merged list is a schema violation.

```python
# Abstract shape — exhaustive checklist, version-scope map, and scoped
# union logic in L3.
roles = parse_named_roles(question_text)
boxes, reviewer_union, author_union, per_loop = tier_1_sweep(
    doc_id, product, roles, target_version)

assert all(v is not None for v in boxes.values()), \
    f"Tier-1 checklist unchecked: {[k for k, v in boxes.items() if v is None]}"

if target_version is not None:
    answer[subq] = {
        "author_employee_ids":       author_union,
        "key_reviewer_employee_ids": reviewer_union,
        "tier_used":                 "tier_1_union",
        "inclusion_width":           "narrow",
        "evidence_sources_checked":  boxes,
    }
else:
    answer[subq] = {
        "author_employee_ids":       author_union,
        "key_reviewer_candidates_per_loop": per_loop,
        "tier_used":                 "tier_1_union_per_loop",
        "inclusion_width":           "AMBIGUOUS",
        "evidence_sources_checked":  boxes,
    }
```

Read `references/tier-1-reviewer-sweep.md` when a question names any
reviewer-like role (`key reviewers`, `approvers`, `feedback providers`)
OR names both an author role and a reviewer role in one sub-question —
the L3 chapter owns the version-scope-per-hit tagging and the
cross-loop leak check. Skip only when the single role is `author(s)` of
a single-version artifact with a populated unambiguous `author` field.

---

### Step 6 — Validate output value: entity-scope first, then source, then form

For any non-employee entity class (URLs, docs, meetings, PRs), run
three probes in order:

1. **Entity-scope probe.** Parse possessives and prepositions to
   determine whose entities are in scope. Ambiguous prepositions
   (`for X products`, `about X`, `on X`, `shared re X`, `related to X`)
   map to AMBIGUOUS entity scope — enumerate BOTH scope readings' value
   lists and emit both arrays.
2. **Source-collection probe.** Values must come from the authoritative
   dataset collection (`dataset.urls`, `dataset.documents`, …). Values
   drawn from a non-authoritative source (e.g., slack message hrefs) are
   a hard fail — re-derive from the collection.
3. **Form probe.** Wording picks `raw` vs `canonical`; sibling-answer
   convention cross-checks. On conflict → `value_form = "AMBIGUOUS"`
   and emit BOTH `values_raw` and `values_canonical` arrays.

```python
# Abstract shape — probes and materialization templates in L3.
scope_tag, scope_a, scope_b = entity_scope_probe(question_text, product_name)
source = source_collection_probe(entity_class, candidates, dataset)
rows   = rederive_from_collection(source, scope_tag, scope_a, scope_b) \
         if source.needs_rederive else source.rows
form   = form_probe(entity_class, question_text, rows)

answer[subq] = materialize(scope_tag, source, form, rows)
```

Read `references/output-schema-conventions.md` when the answer includes
any non-employee entity (URLs, docs, meetings, PRs) OR a scalar metric
field (`tokens`, `cost`, `duration`). Skip when the only output class is
`eid_*` employees and the employee directory check already passes.

---

### Step 7 — Pre-save audit (mechanically checkable)

Before `write_answer_json`, run the audit that checks required keys
(including `inclusion_width` on every role / entity-class sub-question),
AMBIGUOUS materialization (width, form, scope), role separation,
structural-source cross-reference, UNION-ALL default against a narrowing
cue, and scalar type conformance.

**Tokens-provenance rule (anchored here because the `0`-without-provenance
pattern recurs):** every top-level scalar metric needs a provenance
string. Valid: `{"tokens": 12345, "tokens_provenance": "metadata.total_tokens"}`.
Valid failure: `{"tokens": 0, "tokens_provenance": "lookup failed: subagent did not return total_tokens"}`.
Invalid: `{"tokens": 0}` (no provenance), `{"tokens": "N/A"}` (sentinel
string), `{"tokens": 0, "tokens_provenance": "metadata.total_tokens"}`
(provenance claims success for a 0 value).

```python
# Abstract shape — branched audit and corrective actions in L3.
failures = audit(answer, questions, schema)
assert not failures, f"fix before save: {failures}"
write_answer_json(answer)
```

Read `references/literal-wording-audit.md` when the task has ≥2
sub-questions, OR any sub-question names a role, OR any top-level answer
field has a declared scalar type — the L3 chapter owns the UNION-ALL
detector and the branched corrective actions. Skip only when the task is
a single sub-question with no named roles and no scalar metric fields.

---

## Output Format (Strict, JSON-ready)

Every sub-question answer object **must** include these keys
(missing any = schema violation):
- `value_form`: `"raw" | "canonical" | "AMBIGUOUS"`
- `authoritative_source`: named field or collection
- `wording_cue_verbatim`: exact phrase from the question that drove the
  width/form pick, or `null` for AMBIGUOUS
- `evidence_sources_checked`: dict mapping each structural source to its
  hits list (possibly empty)

Role-extraction and non-employee entity-class sub-questions additionally
require:
- `inclusion_width`: `"narrow" | "broad" | "AMBIGUOUS"` (role-extraction
  derives this from the target-version scoping; qualitative-filter
  derives it from the hard wording-cue table)
- role-extraction: `tier_used` plus one `<role>_employee_ids` array per
  role named in the question (or `key_reviewer_candidates_per_loop` when
  `inclusion_width == "AMBIGUOUS"`)
- non-employee entity: `entity_class` plus `entity_scope` (either a
  single scope label or `"AMBIGUOUS"`)

AMBIGUOUS sub-questions emit **both** arrays — never a single `values`
array with `AMBIGUOUS`:
- form AMBIGUOUS → `values_raw` AND `values_canonical`
- width AMBIGUOUS → `values_narrow` AND `values_broad` (or
  `key_reviewer_candidates_per_loop` for role extraction)
- scope AMBIGUOUS → `values_scope_a` AND `values_scope_b` with
  `scope_a_label` / `scope_b_label`

Top-level scalar metrics (`tokens`, `cost`) are numeric and carry a
`<field>_provenance` string; `"N/A"` is invalid and `0` requires a
provenance beginning with `"lookup failed: "`.

```json
{
  "target_product": "<ProductName>",
  "report_doc_id": "<doc_id>",
  "tokens": 12345,
  "tokens_provenance": "metadata.total_tokens",
  "subq_authors_and_reviewers": {
    "author_employee_ids":       ["eid_..."],
    "key_reviewer_employee_ids": ["eid_..."],
    "tier_used":                 "tier_1_union",
    "inclusion_width":           "narrow",
    "value_form":                "canonical",
    "authoritative_source":      "document.reviewers ∪ document.feedback ∪ ...",
    "wording_cue_verbatim":      "key reviewers",
    "evidence_sources_checked":  {"document.reviewers": [...], "...": []}
  },
  "subq_other_entities": {
    "entity_class":          "url",
    "entity_scope":          "AMBIGUOUS",
    "scope_a_label":         "URLs OF <X> products",
    "scope_b_label":         "URLs about <OurProduct> shared for <X>-related work",
    "values_scope_a":        ["https://..."],
    "values_scope_b":        ["https://..."],
    "value_form":            "raw",
    "inclusion_width":       "broad",
    "authoritative_source":  "dataset.urls",
    "wording_cue_verbatim":  null,
    "evidence_sources_checked": {"dataset.urls": [...]}
  }
}
```

### Evidence Map (pointers + minimal snippets)
For each extracted ID, include:
- artifact type + artifact id
- a short snippet that directly supports the mapping
- the inclusion / exclusion rule from Step 0.5 that selected it
- any edge-case classification (ack-only, url-only, clarifying-only,
  context-discussant) with its named-field predicate

---

## Recommendation Types

- **USE_EVIDENCE** — evidence sufficient, product-grounded, Tier-1
  version-scoped union recorded, value forms match wording × sibling
  convention, Step 7 audit passed.
- **NEED_MORE_SEARCH** — missing signals; expand to PRs, slack replies,
  other meetings, dataset-wide reviewer collections, prior document
  versions, share-message threads.
- **AMBIGUOUS** — conflicting product signals, multiple equally valid
  artifacts, no structural anchor for the inclusion/exclusion rule,
  narrow-vs-broad wording silent, version-target silent across multiple
  review loops, entity-scope preposition ambiguous, or value form
  unresolvable. Surface both candidate sets / both forms / both scopes
  with cardinalities.

---

## Common Pitfalls

1) **UNION-ALL default against a narrowing cue.** Pooling every
   gathered candidate from every source — meeting attendees as
   reviewers, ack-only `"Thanks!"` posters as insight-providers,
   post-publication review loops merged into pre-publication reviewer
   sets — when the wording cue (`"key"`, `"primary"`, `"substantive"`,
   `"provided insights"`) requires a filtered subset. Step 7's
   UNION-ALL detector catches this; Step 0.5's cardinality sanity
   check and Step 5's version-scope filter prevent it upstream.
2) **Extraction before planning.** Grabbing IDs before writing a
   falsifiable inclusion rule tied to a named structural field →
   Step 0.5. Subjective labels (`substantive`, `tangential`) and
   hand-built middle buckets are hard fails.
3) **Cross-product leakage.** Picking the same doc type for the wrong
   product because it appears first → Step 2's 2-signal grounding gate.
4) **Single-source commitment / role conflation.** Reading only the
   first share-thread, treating meeting attendees as reviewers, or
   merging authors+reviewers into one flat list → Step 5's Tier-1
   version-scoped UNION checklist + mandatory per-role arrays.
5) **Entity-scope / source / form mis-pick.** Picking the wrong
   scope reading of `for X products` / `about X`, harvesting URLs from
   slack hrefs instead of `dataset.urls`, or picking raw vs canonical
   by one signal only → Step 6 runs the three probes in order; conflict
   on any axis → emit both arrays with the appropriate labels.
6) **Scalar sentinel / unlogged zero.** `"N/A"` or an unlogged `0` in
   `tokens`/`cost`/`duration` → Step 7 pulls from `total_tokens`; `0`
   requires a `"lookup failed: <reason>"` provenance.
7) **Wrong version / version-silent authors.** Draft chosen over
   final/latest, OR the "latest" version's author used silently when
   multiple versions have different authors → Step 3 + Step 4's
   multi-version union rule.
8) **AMBIGUOUS noted verbally but committed anyway.** Writing a single
   `values` array while claiming the pick is AMBIGUOUS on scope, form,
   or width → Step 7's audit rejects this; AMBIGUOUS must materialize
   as both-scope OR both-form OR both-width arrays.

---

## Do NOT Invoke When

- The answer is in a single small known file and location with no cross-references.
- The task is a trivial one-hop lookup, product scope is unambiguous, and the output is a single employee ID.
