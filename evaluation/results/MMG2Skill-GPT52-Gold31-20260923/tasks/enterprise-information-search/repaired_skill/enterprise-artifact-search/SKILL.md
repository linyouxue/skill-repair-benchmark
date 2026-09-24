---
name: enterprise-artifact-search
description: Multi-hop evidence search + structured extraction over enterprise artifact
  datasets (docs/chats/meetings/PRs/URLs), with strict question grounding, anti-distractor
  filtering, evidence-based entity selection, ID validation, JSON-ready outputs, and
  token logging that avoids unsupported installs.
---

## Steps
1. **Ground on the question text (no heuristics):**
   - Read `/root/question.txt` and treat each entry (e.g., `q1`, `q2`, …) as the *only* specification for what to retrieve.
   - For each question, explicitly extract: target product/topic, required entity types (IDs/names/URLs/etc.), and any constraints (“author”, “key reviewers”, “competitor demos”, “from Slack”, “latest”, etc.).
   - Do **not** infer selection criteria from artifact structure (e.g., do not treat “meeting participants” as “reviewers” unless the question says so).
2. **Build a candidate artifact set (wide recall, then filter):**
   - Start with product-scoped containers when available (e.g., `/root/DATA/products/<Product>.json`).
   - Expand to global search only as needed (grep/ripgrep over `/root/DATA` for exact strings from the question: product name, report title, competitor name, URL fragments, doc IDs).
   - Follow references across artifacts (slack ↔ doc links ↔ meeting transcripts ↔ PRs) to reach primary sources.
3. **HARD grounding & anti-distractor gate (prevent cross-product leakage):**
   - Accept a candidate artifact only if it passes **2+ independent grounding signals** relevant to the question’s target scope, such as:
     - Located under the correct product container *and* referenced from product-specific channels/meetings.
     - Title/content explicitly mentions the target product/topic.
     - Appears in a clearly product-scoped channel/meeting series.
     - Link/path includes a product-specific identifier consistent with the target product.
   - Reject artifacts that primarily concern a different product/topic unless the question explicitly requests cross-product comparisons.
4. **Select the correct “version” when multiple candidates exist:**
   - Prefer explicit `latest`/`final` markers; else use most recent date; else use the one most referenced in follow-up discussions tied to the same grounded scope.
5. **Extract entities with evidence-based rules (no role assumptions):**
   - Authors: prefer explicit fields (`author/authors/created_by/owner`), then PR author, then the Slack poster *only if* it clearly introduces the exact artifact.
   - Reviewers/contributors: use explicit reviewer/approver fields first; else include only people who provide **substantive** feedback in doc comments, meeting transcript turns, or Slack thread replies that are clearly tied to the artifact.
   - URLs/items/IDs: extract directly from artifact fields or message text; de-duplicate while preserving order.
6. **Normalize + validate outputs:**
   - Normalize to the requested type (e.g., employee IDs as `eid_...`).
   - Validate every returned employee ID exists in `/root/DATA/metadata/employee.json` (or the dataset’s employee directory).
   - Ensure the final answer for each question is **always a list** (even length-1).
7. **Write results in the required JSON shape:**
   - Write `/root/answer.json` as:
     - top-level dict keyed by question key (`"q1"`, `"q2"`, …),
     - each value is `{"answer": [...], "tokens": "..."}`.
   - Keep `tokens` as a **string**, matching the task’s example schema.
8. **Token logging (avoid failing installs; prefer available tooling; be explicit if approximate):**
   - Do **not** attempt to `pip install` tokenizers in restricted environments.
   - First try to compute token counts using already-available libraries (e.g., `python -c "import tiktoken"`). If available, use it to count tokens for the per-question serialized payload you produce.
   - If no tokenizer library is available, record a transparent string value such as `"approx:<n>"` based on a consistent local heuristic (e.g., character-count/4), rather than implying an exact “consumed tokens” measurement.
   - Never store numeric token values; always store the token field as a string.
## Expected Result
For every question in `/root/question.txt`, `/root/answer.json` contains an entry like:
- `"answer"` is a list (deduplicated, validated, grounded in artifacts),
- `"tokens"` is a **string** computed via an available tokenizer when possible, otherwise transparently marked as approximate (e.g., `"approx:123"`),
and entity selection is driven by explicit question requirements and direct artifact evidence (not assumptions like “participants == reviewers”).
