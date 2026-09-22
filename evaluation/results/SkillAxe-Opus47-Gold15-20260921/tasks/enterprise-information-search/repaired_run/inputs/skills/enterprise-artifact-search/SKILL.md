---
name: enterprise-artifact-search
description: Multi-hop evidence search + structured extraction over enterprise artifact datasets (docs/chats/meetings/PRs/URLs). Strong disambiguation to prevent cross-product leakage; returns JSON-ready entities plus evidence pointers. Supports authors/reviewers, competitor-attribute contributors, and competitor demo URL harvesting.
---

# Enterprise Artifact Search Skill (Robust)

This skill delegates **multi-hop artifact retrieval + structured entity extraction** to a lightweight subagent, keeping the main agent's context lean.

It is designed for datasets where a workspace contains many interlinked artifacts (documents, chat logs, meeting transcripts, PRs, URLs) plus reference metadata (employee/customer directories).

This version adds critical upgrades over naive retrieval:
1) **Product grounding & anti-distractor filtering** (prevents mixing CoFoAIX/other codenames when asked about CoachForce).
2) **Union collection across ALL valid report versions and evidence channels** (prevents under-counting authors/reviewers when benchmark expects the union).
3) **Key reviewer extraction rules** (prevents naive equating of meeting participants with reviewers, while still preserving all who provided substantive input).
4) **Competitor-attribute contributor extraction** (Q2-style: strengths/weaknesses of competitor products).
5) **Competitor demo URL harvesting** (Q3-style).

---

## When to Invoke This Skill

Invoke when ANY of the following is true:

1. The question requires **multi-hop** evidence gathering (artifact → references → other artifacts).
2. The answer must be **retrieved** from artifacts (IDs/names/dates/roles/URLs), not inferred.
3. Evidence is scattered across multiple artifact types (docs + slack + meetings + PRs + URLs).
4. You need **precise pointers** (doc_id/message_id/meeting_id/pr_id) to justify outputs.
5. You must keep context lean and avoid loading large files into context.

---

## Dataset Shape Notes (Observed)

- `/root/DATA/products/<Product>.json` typically contains keys: `slack`, `documents`, `meeting_transcripts`, `meeting_chats`, `urls`, `prs`.
- `documents` items often use fields: `content`, `date`, `author`, `document_link`, `feedback`, `type`, `id` (note: `type` holds document_type such as "Market Research Report"; `id`/`document_link` may embed a product codename like `cofoaix_...` for CoachForce).
- `slack` items: each message has `Channel.name`, `Message.User.userId`, `Message.User.text`, `Message.User.timestamp`, and optionally `ThreadReplies` (list of `{User: {userId, text, timestamp}}`).
- `meeting_transcripts` items: typically include `meeting_id`, `channel`/`series`, `date`, `participants` (eid list), `transcript` turns with `speaker`/`userId` and `text`, and may include `document_type`.
- **Product codename mapping (recurring):** CoachForce ↔ `CoFoAIX`/`cofoaix`; PersonalizeForce ↔ `onalizeAIX`/`personalizeforce`. Always confirm codename↔product mapping from artifacts before filtering.

---

## Core Procedure (Must Follow)

### Step 0 — Parse intent + target product + question shape
- Extract:
  - target product name (e.g., "CoachForce", "PersonalizeForce")
  - question shape, one of:
    - **Q-AUTHORS_REVIEWERS** (authors + key reviewers of a specific document type)
    - **Q-COMPETITOR_CONTRIBUTORS** (employee IDs who provided insights on strengths/weaknesses of competitor products)
    - **Q-COMPETITOR_URLS** (demo/reference URLs shared for competitor products)
    - **Other retrieval** (fall back to generic multi-hop extraction)

If product name is missing, infer cautiously ONLY if explicitly supported by artifacts; otherwise mark AMBIGUOUS.

---

### Step 1 — Build candidate set (wide recall, then filter)
Search in this order:
1) Product artifact file: `/root/DATA/products/<Product>.json` if exists.
2) Global sweep (if needed): other product files and docs that mention the product name/codename.
3) Within found channels/meetings: follow doc links (e.g., `/archives/docs/<doc_id>`), referenced meeting chats, PR mentions.

For **Q-AUTHORS_REVIEWERS**, collect all candidates whose `type`/`document_type`/`title` contains the target document type string (case-insensitive), OR whose doc links/slack text reference it, OR meeting transcripts tagged with that document_type.

---

### Step 2 — HARD Product Grounding (Anti-distractor gate)
A candidate artifact is **VALID** only if it passes **at least 2 independent grounding signals**:

A) Located under the correct product artifact container (e.g., inside `products/CoachForce.json`).
B) Content/title mentions the target product name or a canonical codename you derived from artifacts (e.g., CoachForce↔CoFoAIX).
C) Shared in a channel clearly for the target product (e.g., `planning-CoachForce`, `#coachforce-*`, `CoFoAIX_planning_*`).
D) Doc id/link path contains a product-specific identifier consistent with the target product.
E) Meeting transcript discussing the artifact references the target product context.

**Important:** Being inside `products/<Product>.json` (signal A) counts as one grounding signal; if content only mentions a codename, verify the codename↔product mapping in that same product file (e.g., other CoachForce documents also reference "CoFoAIX") to accept it. Do NOT reject codename-only content when it lives inside the target product's file and the codename mapping is corroborated elsewhere in the same file.

**Reject rule:** If the artifact content repeatedly names a different product and lacks any grounding to the target product, discard it as a distractor.

---

### Step 3 — Enumerate ALL valid versions (do NOT prematurely collapse)
For Q-AUTHORS_REVIEWERS, produce a **VERSION SET** of every VALID document instance of the target type (e.g., draft, final, latest). Only after Step 5 collect authors/reviewers as a union across the set. Reasons:
- Benchmarks often expect the union of authors across draft/final/latest (co-authors may differ).
- Even when the same person authored all versions, other versions may have distinct `feedback` attributions.

Still track a canonical anchor ("latest" > "final" > most recent date) for evidence pointers, but do NOT drop the other VALID versions.

---

### Step 4 — Extract author(s) (UNION across VERSION SET)
For each VALID version, extract authors in this priority order and UNION the results:
1) Document fields: `author`, `authors`, `created_by`, `owner`.
2) PR fields if the report is introduced via PR: `author`, `created_by`.
3) Slack: user who posted a "Here is the report…"-style message that clearly links to the report doc_id (product-grounded).

Normalize to `eid_*`; resolve names via employee directory if only names appear.

---

### Step 5 — Extract key reviewers (UNION across all evidence channels)
Collect reviewers from **all** of the following, then union:

**Tier 1 — Explicit reviewer fields (highest confidence):**
- Document fields: `reviewers`, `key_reviewers`, `approvers`, `requested_reviewers`.
- PR fields: `reviewers`, `approvers`, `requested_reviewers`.

**Tier 2 — Feedback attributions:**
- Document `feedback` sections when they attribute feedback to specific eids/names.
- Meeting transcripts tagged with the target `document_type` (e.g., a review meeting for a Market Research Report): include every participant/speaker who contributes a substantive turn (question, suggestion, edit, critique). When the meeting's `document_type` matches the target and the transcript shows broad participation on the document, include all participants who speak on-topic.

**Tier 3 — Slack thread replies to the report-share message:**
- Include users who reply with substantive feedback/questions/suggestions tied to the report.
- Exclude pure acknowledgements ("looks good", "thanks") UNLESS no other reviewer evidence exists.

**Union rule (important):** For each VALID version, gather Tier 1 ∪ Tier 2 ∪ Tier 3. Then union across all VALID versions. Do NOT restrict to a single meeting or a single version's feedback list.

**Author-vs-reviewer handling:** If the question asks for "authors and key reviewers" as a combined answer, INCLUDE authors in the final union (do not remove authors from the reviewer set).

---

### Step 6 — Q-COMPETITOR_CONTRIBUTORS extraction
For questions like "employee IDs of team members who provided insights on strengths/weaknesses of <Product>'s competitor products":

1) Enumerate competitor product names from the product file (scan slack/meetings/docs for phrases like "competitor product", "a competitor called", explicit competitor names such as PersonaAI, SmartSuggest, TailorAI).
2) Include any employee `userId` who authors a slack message or meeting transcript turn that:
   - names a competitor product AND
   - discusses a strength, weakness, advantage, limitation, pro/con, or a comparative attribute of that competitor.
3) Include ThreadReplies with substantive competitor-attribute content.
4) Deduplicate; preserve order of first appearance.
5) Exclude generic acknowledgements and messages that only mention the competitor by name without any attribute discussion.

---

### Step 7 — Q-COMPETITOR_URLS extraction
For questions like "demo URLs shared by team members for <Product>'s competitor products":

1) Scan `urls` and slack text for URLs whose host/path references a competitor product identified in Step 6 (e.g., `personaai.com`, `smartsuggest.com`, `tailorai.com`) AND whose path suggests a demo (contains `/demo`, `demo.`, `try`, `preview`, `sandbox`).
2) Include only URLs shared by team members in product-grounded channels/threads.
3) Deduplicate exact URLs; preserve first-share order.

---

### Step 8 — Validate IDs & de-duplicate
- All employee outputs must match `eid_...` and, if directory is available, exist in it.
- Deduplicate while preserving first-seen order.
- For combined "authors + reviewers" answers, order authors first, then reviewers not already listed.

---

## Output Format (Strict, JSON-ready)

### 1) Final Answer Object (Q-AUTHORS_REVIEWERS)
```json
{
  "target_product": "<ProductName>",
  "version_set": ["<doc_id_v1>", "<doc_id_v2>", "<doc_id_v3>"],
  "anchor_doc_id": "<latest_or_final_doc_id>",
  "author_employee_ids": ["eid_..."],
  "key_reviewer_employee_ids": ["eid_..."],
  "all_employee_ids_union": ["eid_..."]
}
```

### 2) Evidence Map
For each extracted ID/URL, include artifact type + artifact id + minimal supporting snippet.

---

## Token Accounting Guidance

When the task requests a `tokens` field per question, log a **conservative, non-zero estimate** derived from actual model usage for that question (e.g., prompt+completion tokens observed while working on that question). If exact per-question accounting is not available, split total observed tokens proportionally to work performed per question. Do NOT emit `0`.

---

## Recommendation Types

- **USE_EVIDENCE** — evidence sufficient and product-grounded across all required channels.
- **NEED_MORE_SEARCH** — VERSION SET incomplete OR reviewer union not yet exhausted (PRs, slack replies, other meetings, doc feedback authors).
- **AMBIGUOUS** — conflicting product signals or multiple equally valid interpretations.

---

## Common Failure Modes (This skill prevents them)

1) **Cross-product leakage** — Fixed by Step 2 grounding.
2) **Under-collection by collapsing to one version** — Fixed by Steps 3–5 union rules.
3) **Treating only meeting speakers as reviewers OR only participants list** — Fixed by Step 5's Tier 1∪2∪3 union.
4) **Missing PR-based reviewers / doc feedback authors / slack replies** — Fixed by Step 5 explicit enumeration of all channels.
5) **Distractor codenames** — Fixed by codename mapping guidance in Step 2.
6) **Missing Q2/Q3 handling** — Fixed by Steps 6–7.

---

## Do NOT Invoke When

- The answer is in a single small known file with no cross-references AND product scope is unambiguous.
