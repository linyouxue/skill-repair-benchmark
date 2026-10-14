---
name: enterprise-artifact-search
description: Retrieve and cross-link enterprise artifacts to extract entities with evidence, using schema-first source-of-truth selection, scope grounding, provenance rules, and contract-compliant verification.
---

# Enterprise Artifact Search Skill (Robust)

## Plan & Guardrails (read top-to-bottom)

1. **Classify the output contract first.** For each subquestion: rewrite the target concept as *(verb → provenance → entity)* (e.g., “shared → message/turn evidence → URL”, “reviewed → review artifact/feedback → person”), then list required fields, whether the evaluator expects *all* matches or a top‑K, and what counts as valid evidence.
2. **Pick a source-of-truth path before any heuristics.** Enumerate (a) candidate structured fields/artifact types that encode the concept, and (b) the linking key that ties evidence to the correct target (doc ID, URL, message thread root, artifact reference). Use heuristics only as a fallback, and bind them to that linking key; treat static catalogs (e.g., a URL directory) as validation/enrichment, not provenance.
3. **Ground scope before extracting entities.** If the question is scoped (product/project/team/time window), collect at least two independent grounding signals before accepting any candidate artifact.
4. **Prefer source-of-truth fields over inference.** Only infer roles (e.g., “reviewer”, “insights provider”) from behavior when explicit role/metadata fields are absent after a deliberate search.
5. **Keep one source-of-truth set per deliverable.** Compute qualifying IDs once, then render the final answer directly from that set/list (stable de‑duplication allowed).
6. **Keyword rules are recall, not definition.** Start with inclusive search terms to find candidate evidence, then re-apply a definition aligned to the question (e.g., evaluative judgment vs. mere mention); do not let convenient tokens (“strengths/weaknesses”, “demo”, `endswith('/demo')`) silently become required unless the prompt explicitly requires them.
7. **Token accounting: satisfy hard numeric contracts.** If the output contract requires token counts, write numeric values (not placeholders); try runtime/trace counters first, else compute with a compatible tokenizer, and if neither is possible stop and surface that the contract cannot be satisfied.
8. **Reconcile sets before writing.** Right before producing the final artifact, compute the exact set/list you intend to output, then diff it against the qualifying set from evidence; any discrepancy must be explained by an explicit exclusion rule, otherwise fix the logic and re-render.

## Search & Cross-link

Apply wide-recall search across artifact types (docs, chat, meetings, PRs, URLs), then tighten with scope filters. Follow links/IDs to traverse: doc ↔ slack share ↔ thread ↔ meeting discussion ↔ PR/approval workflow.

```python
import re

def gather_candidates(index, query_terms):
    hits = []
    for item in index:  # mixed artifact records
        text = (item.get("title", "") + " " + item.get("text", "")).lower()
        if any(t.lower() in text for t in query_terms):
            hits.append(item)
    return hits
```

Decision rule: expand search breadth when the primary doc lacks required fields (reviewers/approvers/etc.).

## Scope Grounding (anti-distractor gate)

Accept a candidate artifact only after it passes **2+ independent grounding signals** for the target scope (product/project/team). Examples: container membership, explicit mentions/aliases, scoped channel/meeting series, path conventions, or nearby artifacts that reassert scope.

```python

def grounded(signals):
    # signals is a dict like {"container": bool, "explicit_mention": bool, "channel": bool, "path": bool}
    return sum(bool(v) for v in signals.values()) >= 2
```

Decision rule: reject “first hit wins”; if grounding is weak or mixed, keep searching and mark ambiguity.

Read references/product-grounding.md when multiple similar artifacts exist across scopes and distractors are plausible. Skip when the dataset has only one scope.

## Extract Authors (role fields first)

Extract authors from explicit fields on the doc/PR/work item before using indirect signals (e.g., who shared a link). Resolve names to IDs using a directory only after the artifact is scope-grounded.

```python

def extract_authors(obj):
    for k in ("author", "authors", "created_by", "owner"):
        v = obj.get(k)
        if v:
            return v if isinstance(v, list) else [v]
    return []
```

## Extract Reviewers (do not equate attendees with reviewers)

When asked for “reviewers/approvers/key reviewers”, do **not** map meeting `participants` (invited/attending) to reviewers. Use a tiered strategy: explicit reviewer-like fields → attributed feedback authors → substantive thread replies/turns tied to the target artifact.

```python

def extract_reviewer_ids(primary_obj, linked_objs):
    for k in ("reviewers", "key_reviewers", "approvers", "requested_reviewers"):
        v = primary_obj.get(k)
        if v:
            return v if isinstance(v, list) else [v]
    return []  # fallback requires evidence; see L3
```

Decision rule: if explicit reviewer fields are absent, switch to evidence-based reviewer derivation tied to the target artifact (must cite pointers/snippets per reviewer).

Read references/reviewer-derivation.md when the primary artifact lacks reviewer fields and a meeting/thread is nearby. Skip when explicit reviewer IDs are present.

## Derive “Insights” Authors (evaluative, not acknowledgement)

For questions about who “provided insights” on strengths/weaknesses, separate *topic mention* from *evaluative contribution*. Count an author only when their message/turn contains an evaluative claim (pros/cons, better/worse, strength/weakness) tied to the target topic.

```python
import re

def is_evaluative(text: str) -> bool:
    t = text.lower()
    cues = [r"\bstrengths?\b", r"\bweakness(es)?\b", r"\bpros?\b", r"\bcons?\b",
            r"\bbetter\b", r"\bworse\b", r"\badvantage\b", r"\bdisadvantage\b"]
    return any(re.search(p, t) for p in cues)
```

Decision rule: if the rule is “competitor mention + broad keywords”, you are still at the *recall* stage; add an evaluative classifier and require a supporting snippet for each included author.

Read references/insight-classification.md when “insights/strengths/weaknesses” must exclude acknowledgements and logistics. Skip when the dataset has explicit labeled fields for insights.

## Extract URLs With Provenance (shared/posted/sent)

When the verb implies provenance (“shared/posted/sent/linked in chat”), extract URLs from communication artifacts (Slack messages, thread replies, meeting chat/transcript turns) and attribute each URL to a person + pointer. Use static URL catalogs only to validate that a found URL is in-scope (e.g., a demo link), not to originate the answer.

```python
import re

def urls_in_text(text: str):
    return re.findall(r"https?://[^\s)\]}>\"']+", text or "")
```

Decision rule: if no communication artifact contains the URL, report none found rather than backfilling from a catalog.

Read references/url-provenance.md when questions ask who shared links or which links were shared. Skip when the question is “which URLs exist” (catalog semantics).

## Token Accounting (numeric, contract-compliant)

When the deliverable must include consumed tokens, treat it as mandatory numeric metadata, not “nice-to-have”. Prefer authoritative counters, but never output non-numeric placeholders when the contract requires counts.

```python
import json

def choose_token_count(run_meta: dict, fallback_count: int | None) -> int:
    for k in ("total_tokens", "tokens", "usage"):
        v = run_meta.get(k)
        if isinstance(v, int):
            return v
        if isinstance(v, dict) and isinstance(v.get("total_tokens"), int):
            return v["total_tokens"]
    if isinstance(fallback_count, int):
        return fallback_count
    raise ValueError("Token counts required but unavailable")
```

Decision rule: if only a run-level total is available but per-item tokens are required, write the numeric total and document an allocation rule; do not write "unavailable".

Read references/token-accounting.md when the output schema requires token counts and you do not already have numeric `total/prompt/completion` usage values. Skip when numeric token counts are already provided by the runtime and can be copied directly.

## Assemble Answers Without Truncation

Render outputs directly from the computed qualifying sets. Do not shorten “because it looks long” unless the task explicitly asks for a subset.

```python

def stable_unique(seq):
    seen, out = set(), []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out
```

Decision rule: if you feel compelled to reduce the list, you must add an explicit rule (e.g., top‑K by votes/date) and verify it matches the question.

Read references/consistency-checks.md when you computed entities from multiple sources and need to guarantee none were dropped. Skip when the answer is a single ID.

## Post-write Verification

Before finalizing, validate that each returned entity has a supporting pointer (artifact ID + minimal snippet) and that the written lists match the computed sets.

```python

def assert_no_drops(matched, written):
    missing = [x for x in matched if x not in written]
    if missing:
        raise ValueError(f"Dropped entities: {missing}")
```

## Common Pitfalls

- **Heuristics before source-of-truth:** starting with regex/keyword extraction over chat text before enumerating structured fields and a linking key to the target artifact.
- **Role substitution:** treating attendance/participants as reviewers instead of locating reviewer/approver fields or attributed feedback.
- **Scope leakage:** accepting a similar artifact from another product/project because it appears first.
- **Over-narrow definitions:** turning convenient tokens ("strengths/weaknesses", "demo", URL suffixes) into hard requirements that silently exclude qualifying evidence.
- **Assembly drift:** computing a qualifying set, then writing the final answer from a different or stricter gate.
- **Contract-metadata violation:** outputting placeholders for required numeric fields (especially token counts) instead of retrieving or computing the required numbers.
