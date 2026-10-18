# Tier-1 reviewer sweep — exhaustive, fail-closed, union across sources, version-scoped

Trigger (from SKILL.md Step 5): a sub-question names any reviewer-like role
(`key reviewers`, `approvers`, `feedback providers`, `requested reviewers`)
OR names both an author role AND a reviewer role in the same sub-question.

**Core rule.** The key-reviewer set is the **UNION** of hits across every
populated Tier-1 source, but **union only within a review loop that
terminates at or before the question's target version**. A short-circuit
like `tier_1_hits or share_thread` is wrong — it hides reviewers who only
appear in `document.feedback`, in a later share event's thread, in a
meeting transcript, or in `prs.reviews`. A **cross-loop** union (merging
hits from a review loop that drove a LATER version into the reviewer set
of an EARLIER version) is also wrong — it over-counts post-publication
reviewers as pre-publication reviewers.

---

## The Tier-1 source checklist (fail-closed)

For every target document version, mark each box with
`checked: <empty | hits=[eid_..., eid_...]>` before save. An unchecked box
blocks `answer.json`.

```python
checklist = {
    # Structural fields on the document (every version, not just "latest")
    "document.reviewers":             None,
    "document.key_reviewers":         None,
    "document.approvers":             None,
    "document.requested_reviewers":   None,
    "document.feedback":              None,   # EVERY bullet, EVERY version
    "document.author":                None,   # EVERY version, not just latest

    # Slack: EVERY share event, not just the first
    "share_message_threads":          None,   # list of threads keyed by share date

    # Meeting transcripts referencing doc_id or product
    "meeting_transcripts.participants":        None,
    "meeting_transcripts.speaker_quotes":      None,   # attributed review comments

    # PRs referencing the doc_id or product
    "prs.reviews":                    None,
}
```

Every box's value is a list of `eid_*` (possibly empty). `None` means "not
yet checked" and must not survive to save.

---

## Subroutine 0 — Version-scope map (NEW, runs before union)

Every Tier-1 hit must be tagged with the **version transition** it drove.
A review loop is a directed arc `v_i → v_j`: the loop reviewed `v_i` and
its output appears in `v_j`. The hit's version-scope is `v_j` — the
version whose CONTENT REFLECTS the review.

Mapping rules:
- `document.feedback` bullets attached to version `v_j` ⇒ scope is `v_j`
  (the feedback drove the next revision; the bullet names the loop that
  produced `v_j`).
- Share-message slack thread posted at time `t` ⇒ scope is the earliest
  version whose `date >= t` and whose content differs from the version
  that was shared (the thread drove that revision). If no later revision
  exists, scope is the shared version itself.
- Meeting transcript dated `t` ⇒ scope is the earliest version whose
  content reflects the meeting's bullets/decisions. **Verbatim bullet
  match in a later version is the strongest signal**; absent that, use
  temporal containment (meeting between `v_i` and `v_j` with topical
  overlap ⇒ scope `v_j`).
- `prs.reviews` on a PR that merged into version `v_j` ⇒ scope `v_j`.

```python
def tag_version_scope(hit_source, hit_payload, versions):
    """Return the version-id whose content reflects this review."""
    # Branch A: bullet physically attached to a specific version
    if hit_source == "document.feedback":
        return hit_payload["attached_to_version"]

    # Branch B: meeting bullets appear verbatim in a later version
    if hit_source == "meeting_transcripts.speaker_quotes":
        for v in versions:
            if any(bullet_appears_verbatim(q, v) for q in hit_payload["quotes"]):
                return v.id
        # Fallback: earliest version after the meeting with topical overlap
        return earliest_post_meeting_version(hit_payload["date"], versions)

    # Branch C: slack share threads — scope is the next revision after share
    if hit_source == "share_message_threads":
        return earliest_version_after(hit_payload["thread_time"], versions)

    # Branch D: PR reviews — scope is the version the PR merged into
    if hit_source == "prs.reviews":
        return hit_payload["merged_into_version"]

    # Branch E: structural reviewer fields on a specific version
    return hit_payload["version"]
```

---

## Subroutine 1 — Sweep + version-scope + scoped union

```python
def tier_1_sweep(doc_id, product, question_roles, target_version):
    boxes = {k: None for k in CHECKLIST_KEYS}
    versions = find_all_versions(doc_id)                 # not just "latest"

    # Each hit is a dict: {"eid": "eid_...", "source": "...",
    #                      "scope_version": "<version_id>"}
    hits_by_source = {k: [] for k in CHECKLIST_KEYS}

    # Branch A: structural reviewer fields present on any version
    for v in versions:
        for f in ("reviewers", "key_reviewers", "approvers", "requested_reviewers"):
            for eid in normalize_to_eids(v.get(f, [])):
                hits_by_source[f"document.{f}"].append(
                    {"eid": eid, "source": f"document.{f}",
                     "scope_version": v.id})

    # Branch B: document.feedback bullets
    for v in versions:
        for bullet in v.get("feedback", []) or []:
            for eid in extract_feedback_authors(bullet):
                hits_by_source["document.feedback"].append(
                    {"eid": eid, "source": "document.feedback",
                     "scope_version": v.id})

    # Branch C: EVERY share-message thread
    for share in find_all_share_events(doc_id, product):
        scope = earliest_version_after(share.thread_time, versions)
        for eid in thread_repliers(share.thread_id):
            hits_by_source["share_message_threads"].append(
                {"eid": eid, "source": "share_message_threads",
                 "scope_version": scope})

    # Branch D: meeting transcripts
    for mt in find_meeting_transcripts(doc_id, product):
        for eid in speaker_attributed_review_quotes(mt):
            scope = tag_version_scope(
                "meeting_transcripts.speaker_quotes",
                {"quotes": mt.quotes_by(eid), "date": mt.date},
                versions)
            hits_by_source["meeting_transcripts.speaker_quotes"].append(
                {"eid": eid, "source": "meeting_transcripts.speaker_quotes",
                 "scope_version": scope})
        # Participants recorded but NOT in union (participation ≠ review)
        for eid in mt.participants:
            hits_by_source["meeting_transcripts.participants"].append(
                {"eid": eid, "source": "meeting_transcripts.participants",
                 "scope_version": tag_version_scope(
                     "meeting_transcripts.speaker_quotes",
                     {"quotes": [], "date": mt.date}, versions)})

    # Branch E: PR reviews
    for pr in find_prs_referencing(doc_id, product):
        for eid in reviewer_eids(pr.reviews):
            hits_by_source["prs.reviews"].append(
                {"eid": eid, "source": "prs.reviews",
                 "scope_version": pr.merged_into_version})

    # Branch F: author union across versions (role=author, not reviewer)
    author_union = set()
    for v in versions:
        author_union.update(normalize_to_eids(v.get("author") or v.get("authors") or []))
    hits_by_source["document.author"] = [
        {"eid": e, "source": "document.author", "scope_version": "all"}
        for e in sorted(author_union)]

    # Populate boxes with just the eid lists (for the fail-closed check)
    for k, hits in hits_by_source.items():
        boxes[k] = sorted({h["eid"] for h in hits})

    # VERSION-SCOPED UNION
    scoped_reviewer_union = scoped_union(
        hits_by_source, target_version, versions,
        reviewer_sources=("document.reviewers", "document.key_reviewers",
                          "document.approvers", "document.requested_reviewers",
                          "document.feedback", "share_message_threads",
                          "meeting_transcripts.speaker_quotes", "prs.reviews"))

    # When target_version is silent, surface each loop separately
    per_loop = per_loop_candidates(hits_by_source, versions)

    if "author" in question_roles and "reviewer" in question_roles:
        scoped_reviewer_union -= set(boxes["document.author"] or [])

    return boxes, sorted(scoped_reviewer_union), sorted(boxes["document.author"] or []), per_loop
```

```python
def scoped_union(hits_by_source, target_version, versions, reviewer_sources):
    """Union only over hits whose scope_version terminates at or before target."""
    terminates_at_or_before = version_ancestry_set(target_version, versions)
    out = set()
    for src in reviewer_sources:
        for h in hits_by_source[src]:
            if h["scope_version"] in terminates_at_or_before:
                out.add(h["eid"])
    return out


def per_loop_candidates(hits_by_source, versions):
    """Group reviewer hits by their scope_version → candidate set per loop."""
    loops = {}
    for src, hits in hits_by_source.items():
        if src in ("document.author", "meeting_transcripts.participants"):
            continue
        for h in hits:
            loops.setdefault(h["scope_version"], set()).add(h["eid"])
    return {v: sorted(eids) for v, eids in loops.items()}
```

---

## Branching: target version silent vs. specified

```python
if target_version is not None:
    # Union within loops terminating at or before target_version.
    answer_reviewers = scoped_reviewer_union
    inclusion_width  = "narrow"       # scoped to one loop or an ancestor chain
else:
    # No version specified. Each loop is a separate candidate.
    # Default: AMBIGUOUS width with per-loop cardinalities.
    if len(per_loop) == 1:
        answer_reviewers = next(iter(per_loop.values()))
        inclusion_width  = "narrow"
    else:
        answer_reviewers = None       # emit per-loop arrays instead
        inclusion_width  = "AMBIGUOUS"
```

AMBIGUOUS materialization in this case:
```python
answer[subq] = {
    "author_employee_ids":       authors,
    "inclusion_width":           "AMBIGUOUS",
    "key_reviewer_candidates_per_loop": per_loop,  # {version_id: [eid,...]}
    "tier_used":                 "tier_1_union_per_loop",
    "evidence_sources_checked":  boxes,
}
```

---

## Worked example — CoFoAIX MRR with three versions

- `v1 = draft`, `v2 = final (2026-04-15)`, `v3 = latest (post-final)`.
- `document.feedback` bullets attached to `v2 (final)` cite three slack
  reviewers (`eid_f98d7490, eid_2d72674d, eid_4f30e22e`) whose comments
  map verbatim to the final's feedback field. **Scope = v2.**
- `CoFoAIX_planning_1` meeting occurred AFTER `v2`'s publication; its
  bullets appear verbatim in `v3 (latest)`. **Scope = v3.**
- Question: "authors AND key reviewers of the final MRR" ⇒ target = `v2`.
- `scoped_union` with `target_version=v2` includes ONLY hits whose
  scope_version is in the ancestor chain `{v1, v2}`. The meeting
  participants hit at `v3` are **excluded**.
- Result: `key_reviewer_employee_ids = [eid_f98d7490, eid_2d72674d, eid_4f30e22e]`.
- The 7 CoFoAIX_planning_1 attendees are **not** merged into the final's
  reviewer set — they are the final→latest loop's reviewers, surfaced
  only if the question targets `v3` or is silent on version (AMBIGUOUS).

Common failure this prevents: unioning all 11 IDs (author + 3 slack + 7
meeting participants) for a question that targets the final version. The
version-scope filter cuts the 7 post-final attendees out of the final's
reviewer set.

---

## Precondition: role separation

Before the sweep fires, parse the roles named in the question. If the
question names `authors AND key reviewers` (or any analogous pair), the
output MUST emit two arrays:

```python
roles = parse_named_roles(question_text)
if len(roles) >= 2:
    required_keys = {f"{r}_employee_ids" for r in roles}
    assert required_keys.issubset(answer[subq].keys()), \
        f"role separation missing: need {required_keys}"
```

A flat merged list like `"authors_and_reviewers": [...]` is a schema
violation that blocks save.

---

## Verification (post-sweep, pre-save)

```python
boxes, reviewers, authors, per_loop = tier_1_sweep(
    doc_id, product, roles, target_version)

# 1. Every checklist box must be non-None (checked).
unchecked = [k for k, v in boxes.items() if v is None]
assert not unchecked, f"Tier-1 unchecked boxes: {unchecked}"

# 2. Every reviewer hit carries a scope_version tag (no untagged hits).
assert all("scope_version" in h for src in hits_by_source
           for h in hits_by_source[src]), "untagged Tier-1 hit"

# 3. Cross-loop detector: if target_version is specified, no hit from a
#    loop that terminates AFTER target_version may appear in the reviewer
#    union.
if target_version is not None:
    allowed = version_ancestry_set(target_version, versions)
    leaked = [v for v in per_loop if v not in allowed
              and any(e in reviewers for e in per_loop[v])]
    assert not leaked, f"cross-loop leak: hits from {leaked} in reviewer union"

# 4. If reviewer_union is empty but structural fields were populated:
#    this signals a target-version/product mismatch — re-read the question.
if not reviewers and any(boxes[s] for s in
                          ("document.reviewers", "document.feedback")):
    log("Tier-1 reviewer_union empty despite structural hits — "
        "likely target-version or product mismatch; re-read question before Tier-2")

# 5. Audit log.
log({"tier_used": "tier_1_union", "boxes": boxes,
     "reviewer_union": reviewers, "author_union": authors,
     "per_loop_candidates": per_loop,
     "target_version": target_version})
```

**Corrective action on failure.**
- `unchecked` non-empty: do NOT save. Return to the sweep and fill the
  missing boxes. If a source does not exist in the dataset (e.g., no PRs
  reference the doc), mark its box as `checked: empty` with a one-line
  reason — do not leave it `None`.
- `untagged Tier-1 hit`: run `tag_version_scope` on each hit before
  calling `scoped_union`. An untagged hit cannot be scoped and is a hard
  fail.
- `cross-loop leak`: remove the leaking eids from the reviewer union.
  Those eids belong to a later review loop — surface them in
  `key_reviewer_candidates_per_loop` for the audit, not in the primary
  array.
- `empty reviewer_union despite structural hits`: re-read the question
  for the correct target doc/version/product; target may be wrong.
