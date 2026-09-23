---
name: enterprise-artifact-search
description: Multi-hop evidence search and structured extraction over enterprise artifacts with strict grounding and an unskippable completion gate that writes and schema-validates the required answer JSON.
---

# Enterprise Artifact Search Skill (Robust)

## TERMINATION SENTINEL (read first; do not skip)

Before `end_turn`: **WRITE** the required answer JSON to the exact required path (default `/root/answer.json`), then **READ-BACK** + **SCHEMA-VALIDATE** it; do not do any other “final step” until this passes.

Read references/finalize_answer_json.md when the deliverable is an answer file (e.g., `/root/answer.json`) and you must guarantee it exists and matches schema. Skip when the harness explicitly guarantees the file is already written and schema-correct.

---

BEFORE `end_turn`: write `/root/answer.json` then read-back + schema-validate it.

This skill delegates **multi-hop artifact retrieval + structured entity extraction** to a lightweight subagent, keeping the main agent’s context lean.

It is designed for datasets where a workspace contains many interlinked artifacts (documents, chat logs, meeting transcripts, PRs, URLs) plus reference metadata (employee/customer directories).

This version adds two critical upgrades:
1) **Product grounding & anti-distractor filtering** (prevents mixing similarly named reports across products).
2) **Key reviewer extraction rules** (prevents “participants == reviewers”; prefers explicit reviewer fields or evidenced feedback).

---

## Termination rule (hard stop)

Do not end the run until the required output artifact is written and validated.

Even if you never invoked this skill (or any other tool) during the run, you must still run the completion gate below before terminating.

---

## When to Invoke This Skill

Invoke when ANY of the following is true:

1. The question requires **multi-hop** evidence gathering (artifact → references → other artifacts).
2. The answer must be **retrieved** from artifacts (IDs/names/dates/roles), not inferred.
3. Evidence is scattered across multiple artifact types (docs + chats + meetings + PRs + URLs).
4. You need **precise pointers** (doc_id/message_id/meeting_id/pr_id) to justify outputs.
5. You must keep context lean and avoid loading large files into context.

---

## Finalize (Required): hard completion gate (block termination)

Immediately before ending the run, run a **non-optional completion gate** and **do not terminate** until it passes.

This gate is mandatory even if you never invoked the skill during the run.

Minimal checklist (must all be true):
1) **WRITE**: you performed an explicit file write action (python write or write tool) to the required path.
2) **READ-BACK**: you re-opened the file from disk and JSON-parsed it.
3) **VALIDATE**: you asserted schema + required question keys; if any check fails, fix and re-run the gate.

Generic gate snippet (write → read-back → validate):

```python
import json
from pathlib import Path

out_path = Path("/root/answer.json")
payload = {"q1": {"answer": [], "tokens": 0}}

out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
loaded = json.loads(out_path.read_text())

assert out_path.exists(), "output file missing (wrong path or write failed)"
assert isinstance(loaded, dict) and loaded, "top-level must be a non-empty dict"
for k, v in loaded.items():
    assert isinstance(v, dict) and "answer" in v and "tokens" in v
    assert isinstance(v["answer"], list), f"{k}.answer must be a list"
    assert isinstance(v["tokens"], int), f"{k}.tokens must be an int"
```

Decision rule: treat file-write + read-back validation as the **last action** in the run; if any assertion fails, fix the payload/path and re-run the gate before doing anything else.

Read references/finalize_answer_json.md when producing a benchmarked deliverable answer file (including the default `/root/answer.json`). Skip when the harness explicitly guarantees the file is already written and schema-correct.

---

## Why Use This Skill?

**Without this skill:** you manually grep many files, risk missing cross-links, and often accept the first “looks right” artifact (common failure: wrong product).

**With this skill:** a subagent:
- locates candidate artifacts fast
- follows references across docs/chats/meetings/PRs
- extracts structured entities (employee IDs, doc IDs)
- **verifies scope/grounding** to reject distractors
- returns a compact evidence map with artifact pointers

Typical context savings: **70–95%**.

---

## Invocation

Use this format:

```python
Task(subagent_type="enterprise-artifact-search", prompt="""
Dataset root: /root/DATA
Question: <paste the question verbatim>

Output requirements:
- Return JSON-ready extracted entities (employee IDs, doc IDs, etc.).
- Provide evidence pointers: artifact_id(s) + short supporting snippets.

Constraints:
- Avoid oracle/label fields (ground_truth, gold answers).
- Prefer primary artifacts (docs/chat/meetings/PRs/URLs) over metadata-only shortcuts.
- MUST enforce grounding: only accept artifacts proven to be in-scope for the target entity/product.
""")
```

---

## Core Procedure (Must Follow)

### Step 0 — Parse intent + target scope
- Extract:
  - target scope identifier(s) (e.g., a product name, customer, team)
  - entity types needed (authors, reviewers, owners, dates, IDs)
  - artifact types likely relevant (docs, review threads, meetings, PRs)

If the target scope is missing in the question, infer cautiously from nearby context ONLY if explicitly supported by artifacts; otherwise mark AMBIGUOUS.

---

### Step 1 — Build candidate set (wide recall, then filter)
Search in this order:
1) Scope-specific artifact container(s) if present (e.g., `products/<X>.json`).
2) Global sweep (if needed): other containers and docs that mention the scope identifier.
3) Within found chats/meetings: follow doc links, referenced meetings, PR mentions.

Collect all candidates that match the requested artifact type/name pattern (case-insensitive) and retain their artifact IDs for later evidence pointers.

---

### Step 2 — HARD Grounding (Anti-distractor gate)
A candidate artifact is **VALID** only if it passes **at least 2 independent grounding signals**.

Grounding signals (choose any 2+):
A) Located under the correct scope container AND linked from that scope’s channels/meetings.
B) Content/title explicitly mentions the target scope identifier or a canonical alias list derived from artifacts.
C) Shared in a clearly scope-specific channel/meeting series.
D) Link path or artifact ID contains a scope-specific identifier consistent with the target scope.
E) A meeting/chat discussing the artifact includes the target scope context in title/channel references.

Reject rule:
- If the artifact repeatedly names a different scope and lacks grounding for the target scope, mark as DISTRACTOR and discard.

---

### Step 3 — Select the correct version
If multiple VALID candidates exist, choose the best match by this precedence:

1) Explicit “latest” marker or most recent date field
2) Explicit “final” marker
3) Otherwise, most recent by date
4) If dates missing, choose the one most referenced in follow-up discussions

Keep the selected artifact’s primary ID/link as the anchor.

---

### Step 4 — Extract author(s)
Extract authors in this priority order:
1) Document fields: `author`, `authors`, `created_by`, `owner`
2) PR fields if introduced via PR: `author`, `created_by`
3) Chat: the user who posted the message that clearly links to the anchored artifact

Normalize into canonical IDs:
- If already normalized (e.g., `eid_...`), keep it.
- If only a name appears, resolve via a directory (name → ID) only after grounding the artifact.

---

### Step 5 — Extract key reviewers (do not equate “participants” with reviewers)
Key reviewers must be **evidence-based contributors**, not simply attendees.

Priority order:

Tier 1: explicit reviewer fields
- Doc/PR fields like `reviewers`, `key_reviewers`, `approvers`, `requested_reviewers`

Tier 2: explicit feedback authors
- Attributed feedback sections or transcript turns that contain concrete suggestions/edits

Tier 3: chat thread replies
- Include only substantive feedback tied to the anchored artifact
- Exclude pure acknowledgements unless no other reviewer evidence exists

Critical rule:
- A participants list alone is insufficient; count someone only with explicit reviewer fields or evidenced feedback.

---

### Step 6 — Validate IDs & de-duplicate
- All outputs must be valid canonical IDs and exist in the relevant directory if provided.
- Remove duplicates while preserving role order:
  1) authors first
  2) key reviewers next

---

## Output Format (Strict, JSON-ready)

Return:

### 1) Final Answer Object
```json
{
  "target_scope": "<ScopeName>",
  "artifact_id": "<doc_id_or_other_id>",
  "author_ids": ["id_..."],
  "key_reviewer_ids": ["id_..."],
  "all_ids_union": ["id_..."]
}
```

### 2) Evidence Map (pointers + minimal snippets)
For each extracted ID, include:
- artifact type + artifact id
- a short snippet that directly supports the mapping

---

## Recommendation Types

Return one of:
- **USE_EVIDENCE** — evidence sufficient and grounded
- **NEED_MORE_SEARCH** — missing reviewer signals; expand search (PRs, chat replies, other meetings)
- **AMBIGUOUS** — conflicting grounding signals or multiple equally valid candidates

---

## Common Pitfalls

- Ending the run without writing the required output artifact; always pass the completion gate (write + read-back + schema check) before terminating, even if you never invoked this skill.
- Accepting the first matching artifact without grounding it to the target scope (cross-scope leakage).
- Treating attendance/participants as reviewers; require explicit reviewer fields or evidenced feedback.
- Choosing a draft when a later/final artifact exists; apply version selection rules.
- Returning the wrong schema shape (e.g., scalar instead of list); enforce invariants and validate by read-back.
