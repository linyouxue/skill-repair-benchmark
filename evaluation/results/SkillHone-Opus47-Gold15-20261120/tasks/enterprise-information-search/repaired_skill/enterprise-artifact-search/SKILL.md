---
name: enterprise-artifact-search
description: Multi-hop evidence search + structured extraction over enterprise artifact datasets (docs/chats/meetings/PRs/URLs). Resolves product codenames and competitor-vs-own-product scope; returns JSON-ready entities plus evidence pointers for one or many related questions.
---

# Enterprise Artifact Search Skill

Reusable skill for retrieving answers over enterprise artifact workspaces
(documents, slack-style chats, meeting transcripts, PRs, URL catalogs, plus
reference metadata such as an employee or customer directory).

It is tuned to the common failure modes of this kind of dataset:

- A product can appear under its **public name** and under one or more
  **internal codenames** (channel/meeting/document identifiers often use the
  codename). Confusing the codename with a distractor loses the correct
  evidence.
- **Multiple products may have the same artifact type** (e.g. a "Market
  Research Report" exists for several products). Picking the first hit is a
  frequent loss.
- **"Who reviewed X"** ≠ "who attended the review meeting". Attendance is a
  weak signal; explicit feedback is the strong signal.
- **Competitor-vs-own-product scope**: questions that ask about "competitor
  products" require excluding evidence about the host product itself (and
  vice versa).
- Benchmarks typically require a strict output schema (one JSON object with
  per-question entries, lists of IDs, and a reported token count).

The skill delegates the heavy retrieval to a focused subagent so the main
agent's context stays small; **do not read large product JSON files directly
into the main agent's context**.

---

## When to Invoke

Invoke when ANY of the following is true:

1. The question requires **multi-hop** evidence gathering (artifact →
   references → other artifacts).
2. The answer must be **retrieved from artifacts** (IDs / names / dates /
   URLs / roles), not inferred.
3. Evidence is scattered across multiple artifact types (docs + chat +
   meetings + PRs + URLs).
4. You need **precise pointers** (doc_id / message_id / meeting_id / pr_id)
   to justify outputs.
5. The user supplies a **batch of related questions** (`q1`, `q2`, ...) and
   asks for a single structured JSON answer file.

Do NOT invoke when the answer is in a single small known file with no
cross-references and the product scope is unambiguous.

---

## Invocation

```python
Task(subagent_type="enterprise-artifact-search", prompt="""
Dataset root: <root, e.g. /root/DATA>
Question file: <e.g. /root/question.txt>  # may contain q1..qN
Output file:   <e.g. /root/answer.json>

Required output schema (strict):
{
  "q1": {"answer": [...], "tokens": <int>},
  "q2": {"answer": [...], "tokens": <int>},
  ...
}

Rules:
- Every answer value is a JSON LIST, even when there is a single item.
- IDs must match the dataset's ID pattern (e.g. employee IDs `eid_...`).
- Preserve evidence pointers internally and attach a short justification
  per question in your final message to the user, but keep the saved JSON
  strictly in the schema above (plus the `tokens` field per question).

Constraints:
- Do not use oracle/label fields (ground_truth, gold, expected_*).
- Prefer primary artifacts (docs / chat / meetings / PRs / URLs) over
  metadata-only shortcuts.
- Resolve product codenames before filtering (see Step 1 below).
- Separate "own product" vs "competitor" scope before extracting.
""")
```

---

## Dataset Shape (what to expect, generically)

A typical workspace under the dataset root has:

- `metadata/` — directories such as `employee.json`, `customers_data.json`,
  team lists.
- `products/<ProductName>.json` — a per-product bundle. Each bundle usually
  contains fields like `documents`, `slack_messages` (or similar chat
  arrays), `meeting_transcripts`, `prs` / `pull_requests`, `urls`, and a
  `channels` list. Field names vary; discover them before assuming.

Always start by **listing** the dataset tree and **printing the top-level
keys** of a relevant product bundle before extracting. Never load an entire
bundle into the main agent's answer.

---

## Core Procedure

### Step 0 — Parse the question set and intent

For each question extract:

- target product(s) by name
- whether the scope is "the target product itself" or "its competitors"
- entity types required (employee IDs, doc IDs, URLs, dates, ...)
- artifact types most likely to hold the answer (docs vs meetings vs
  chat vs PRs vs URL catalog)

Keep this as a per-question plan; the questions in one batch are usually
independent.

### Step 1 — Resolve product aliases / codenames (critical)

Before filtering, build an alias set for the target product:

1. Open `products/<TargetProduct>.json` and scan its documents, slack
   messages, meeting titles and channel names for **codename patterns**:
   - a short all-caps token that recurs in channel names (`planning-XYZ`),
     meeting ids (`XYZ_planning_1`), and document ids / titles;
   - phrases like "internal codename", "aka", "formerly", or a parenthetical
     short name next to the public name.
2. Treat any such token as an **alias of the target product**, not as a
   distractor, when it appears inside the target product's own bundle,
   channels, or meeting series.
3. If a token appears **only** in another product's bundle / channels /
   meetings, treat it as that other product's name.

Record the resolved alias set as `{target_product, aliases: [...]}` and use
it everywhere downstream. **Never hard-code which token is the codename —
derive it from the data in this run.**

### Step 2 — Build the candidate set (wide recall, then filter)

Search in this order, scoped to the alias set from Step 1:

1. The target product's own bundle.
2. Channels whose name contains the product name or any alias.
3. Meeting series whose id/title contains the product name or any alias.
4. Cross-references (doc links, PR mentions, slack thread replies).

Filter candidates by the artifact type the question asks for (e.g.
`document_type == "Market Research Report"`, or messages mentioning "demo"
and a URL, etc.).

### Step 3 — Product grounding (anti-cross-leakage)

A candidate artifact is **in-scope** only if **at least two** of these
independent signals point to the target product (using the Step-1 alias
set):

A. It lives under the target product's bundle AND is referenced from a
   channel/meeting of that product.
B. Its content/title explicitly names the target product or one of its
   aliases.
C. It is shared in a channel whose name is clearly for the target product.
D. Its id/link path contains a token from the target product's alias set
   and not a token exclusive to another product.
E. A meeting transcript that discusses it belongs to the target product's
   meeting series.

Reject candidates whose only grounding signal is "appears near the target
product's name" if their content and identifiers are about a different
product. Do **not** reject a candidate solely because it uses the target
product's internal codename — that is expected.

**Co-bundled foreign-product detection (critical):** a single
`products/<TargetProduct>.json` bundle sometimes includes channels,
meetings, documents, and chat traffic belonging to **another product**
(a sibling / predecessor / related initiative with its own public name
and its own channels). Before iterating over channels for Step 6 / Step
7, build the set of channel names that are **outside** the target
product's alias set — if a channel's name contains a product-like token
that is not in the target's aliases and that is not a generic team
word, treat the channel as foreign and exclude its messages entirely
from reviewer / insight / URL extraction. The same applies to meeting
series whose ids reference a foreign product name.

### Step 4 — Select the correct version (if multiple valid candidates)

Datasets often carry several variants of the same artifact (for example
`<id>`, `final_<id>`, `latest_<id>` with increasing dates). Decide first
whether the question is about **one specific version** or about the
**artifact as a whole**:

- *Version-specific* ("final X", "latest X", "the X dated ..."): pick a
  single anchor using the precedence below.
- *Singular-definite without a version qualifier* ("authors and
  reviewers of **the** X", "who worked on **the** X"): **default to the
  single most-polished version** — the one explicitly marked `final_...`
  or `latest_...` or dated last. The author of the artifact is taken
  from this anchor's `author` field, and the reviewer evidence is
  gathered from the discussion/meeting of this anchor's version only.
  Do **not** union across every earlier draft by default — each earlier
  draft usually corresponds to a *different* review discussion whose
  participants are reviewers of **that** draft, not of the artifact as
  released. Over-inclusion (listing every draft's reviewers) is a
  common cause of failure on these questions.
- *Explicit whole-artifact* ("all versions of X", "every reviewer who
  ever touched X", "evolution of X across drafts"): treat all in-scope
  versions as co-equal anchors and take the **union** of per-version
  authors and reviewers (de-duplicated, order-preserved). Use this mode
  only when the question's wording explicitly asks for cross-version
  history.

Precedence when a single anchor is needed:

1. Explicit `latest` marker in id / title / link, or an explicit "final"
   marker. If both `final_...` and `latest_...` exist, prefer the one
   with the later `date` (usually `latest_...`).
2. Most recent `date` / `updated_at` field.
3. Most frequently referenced in follow-up discussion (slack replies,
   meeting chats).

Record each chosen anchor id and link. When using the union mode, also
record the per-version meeting(s), PR(s) and chat thread(s) that discuss
each version — Step 6 iterates over all of them.

**Cross-check against the artifact's own `feedback`-like field.** Each
version typically carries its own feedback list; the reviewers of a
version are the attribution targets of that version's bullets (Step 6
Tier 1). A single-anchor question therefore produces reviewers only
from **one** feedback list, not from the concatenation of every draft's
feedback. If you find yourself about to admit reviewers sourced from a
feedback list belonging to a different version than the chosen anchor,
stop — you have slipped from single-anchor into union mode.

### Step 5 — Extract author(s)

Priority order:

1. Document fields: `author`, `authors`, `created_by`, `owner`.
2. PR fields if the doc is introduced via PR: `author`, `created_by`.
3. The chat user who posts "Here is the report ..." **only when** the
   message links to the chosen doc and is product-grounded.

Normalize to the dataset's canonical ID pattern via the directory
(`metadata/employee.json` or equivalent).

### Step 6 — Extract reviewers / contributors (evidence-based)

Attendance is NOT enough. Use this priority **and iterate over every
in-scope anchor / discussion venue from Step 4 (do not stop at the first
hit)**:

**Tier 1 — explicit fields on the artifact:**
- Document: `reviewers`, `key_reviewers`, `approvers`, `requested_reviewers`.
- Document: a `feedback` / `feedback_items` / `comments` field whose
  entries list the suggestions applied to this version. **This is often
  the single strongest signal and is easy to miss** — always print the
  document's top keys and inspect any feedback-like field before falling
  back to meetings. The field may be either:
  (a) a structured list that attributes each item to a specific
      employee/user ID — take those IDs directly as key reviewers; or
  (b) a plain-text bulleted list of suggestions without speaker tags —
      in this case treat the bullets as **evidence targets** and attribute
      each bullet to the speaker whose transcript turn (from Tier 2's
      review meetings) or whose chat turn (from Tier 3's discussion
      thread of that version) most clearly produced that suggestion. A
      reviewer is a transcript/chat speaker whose turn is the source of
      at least one bullet in the final feedback list. Participants who
      only attended or only made non-substantive turns (acknowledgements,
      scheduling, "looks good") but whose content is **not reflected**
      in the feedback bullets are NOT reviewers of that version.
  **Hard upper bound and per-bullet citation (critical):**
  - First *count the bullets* in the feedback list for this version.
    The reviewer set contributed by this version has **at most** that
    many distinct speakers. A review meeting with more participants than
    bullets necessarily means some participants did not contribute a
    bullet — they are excluded.
  - For each bullet, record the specific transcript/chat turn you treat
    as its source. The match must be **direct**: the same concrete
    suggestion, the same example, the same recommendation phrasing or
    noun phrase — not merely the same topic area. A bullet like "add
    more depth to section Y" maps to the turn that asked for that
    specific depth; it does NOT map to a different turn that only
    mentioned section Y in passing or raised an unrelated question.
  - If you cannot cite a specific bullet whose content traces back to a
    given speaker's turn, that speaker is NOT a reviewer of that version
    — regardless of how substantive or expert their turn was.
  - Do NOT assume "all meeting participants gave feedback" or "all
    attendees of a review meeting are reviewers." That is the exact
    failure mode this tier is designed to prevent.
- When several versions exist, each version's `feedback` field may
  attribute to a *different* subset of speakers; take the union across
  all versions (see Step 4's union mode).
- PR: `reviewers`, `approvers`, `requested_reviewers`, `review_comments`.

**Tier 2 — attributable feedback in meeting transcripts:**
- Enumerate **every** meeting whose title / `document_type` / topic matches
  the artifact (e.g. meeting series `<codename>_planning_1`,
  `<codename>_planning_2`, ...). If a meeting's `document_type` names the
  artifact type, treat it as a review venue for that artifact.
- Parse the transcript **turn by turn** (lines of the form
  `"<Name>: <utterance>"`) and keep every speaker whose turn contains
  concrete suggestions / edits / critiques / questions about the artifact
  content. Resolve each speaker name to an employee ID via the directory.
- **Prefer bullet-grounded attribution over meeting-participation.** When
  the document carries a plain-text `feedback` list (Tier 1 case b),
  match each bullet to the transcript turn whose content is the clearest
  source for that bullet. The reviewer set is the authors of those
  source turns, **not the full attendee list** of the review meeting.
  Participants who were present but whose turns are not reflected in the
  final feedback bullets are excluded.
- Do **not** count participants who only appear in an attendees list, only
  say "looks good" / "thanks", or only ask logistical/scheduling
  questions.
- When a review meeting is held for a specific version, take the union of
  substantive (bullet-grounded) speakers across all review meetings of
  the artifact.

**Tier 3 — substantive thread replies and flat-thread siblings in chat:**
- For each chat message that shares the artifact (links to its doc id or
  names it), expand the message's `ThreadReplies` / `replies` /
  `thread_messages` field (field names vary — inspect the message keys).
  Keep every distinct user whose reply contains concrete feedback,
  suggestions, questions, strengths/weaknesses, or comparisons about the
  artifact.
- **Flat-thread detection (critical):** many enterprise chat exports in
  this family store conversations as a flat list of top-level messages in
  the same channel rather than as nested `ThreadReplies`. If the share
  message's reply field is empty **or absent**, do NOT conclude the
  discussion is empty. Instead, enumerate every top-level message in the
  **same channel** whose timestamp falls in a reasonable window after the
  share (e.g. within a few hours or until the next unrelated topic opens)
  and which addresses the share (names the artifact, quotes a section,
  `@`-tags the share author, answers a question in-thread, or continues
  the same subject). Those sibling top-level messages are the de-facto
  thread and their authors count exactly like `ThreadReplies` authors.
- Also consider substantive top-level messages in the same channel that
  are explicitly responding to the share (quoting the artifact title or
  the share author).
- Exclude pure acknowledgements ("thanks", "lgtm", ✅-only, etc.) unless
  they are the only evidence available for a user already strongly
  grounded by Tier 1 or Tier 2. Also exclude bot/system messages
  (whatever bot/admin account id the export uses — typically something
  like a channel-admin bot), channel-created / joined notifications, and
  `@`-mention-only turns with no content of their own.

**Union across tiers and versions:**
- The final reviewer set is the **union** of users identified in Tier 1
  through Tier 3, de-duplicated while preserving first-seen order.
- When a question asks for *authors AND reviewers together* (common
  phrasing: "authors and key reviewers of X"), include the author(s) at
  the head of the list, followed by the reviewer union. When the question
  asks only for reviewers, exclude the author(s) unless the author also
  provides substantive reviewer-style feedback on another version.

**Exclusions:**
- Attendees of unrelated meetings (meetings whose topic is a different
  artifact type or a different product) are excluded.
- Users whose only mention is being `@`-tagged by someone else are
  excluded unless their own turn contains substantive content.

If evidence disagrees between tiers, prefer Tier 1 and record the
mismatch in your evidence notes.

### Step 7 — Competitor vs own-product scope

Questions about **"competitor products"** of X require:

1. Identify the competitor set for X. Look for:
   - a `competitors` / `competitor_products` field on the product bundle;
   - URL catalog entries labeled as competitor demos / docs;
   - slack/meeting mentions of "competitor", "alternative", "vs.";
   - message patterns like "I was reading about <Name>, a competitor
     product" — the `<Name>` is a competitor.
2. When extracting answers, keep ONLY evidence whose subject is a competitor
   name. Discard mentions whose subject is X itself.
3. For URL questions, filter the URL catalog by host/path/label matching
   the competitor set; exclude URLs whose host or label matches X or its
   aliases. Also inspect **chat messages** for any `https?://` link whose
   host matches a competitor; a competitor demo URL may be shared in chat
   even if it is also listed in the catalog.

**"Insights on strengths and weaknesses of competitors" — who to count:**

- A user qualifies **only** when their own turn (top-level or reply)
  discusses a **named competitor product** of X — not X itself, not a
  general industry trend — with substantive content about that
  competitor's features, capabilities, limitations, pricing,
  differentiation, strengths, weaknesses, opportunities, or threats.
  Both the OP of a competitor thread and any subsequent contributor who
  adds an observation about the same named competitor count.
- Iterate over both top-level messages and **ThreadReplies** (or the
  dataset's equivalent nested reply field). A user who replies to a
  competitor thread with an added weakness or strength counts too.
- **When `ThreadReplies` is empty or absent**, the discussion is almost
  certainly a *flat thread* carried in same-channel sibling top-level
  messages (see Step 6 Tier 3). For every competitor discussion you
  find, sort the channel's messages by timestamp and walk forward from
  the OP: every subsequent message (until a clearly new topic starts)
  that references **the same named competitor**, asks a probing
  question about it, confirms/adds a strength or weakness, or contrasts
  it with the own product is part of the same discussion and its author
  counts.
- Probing comparison questions ("Is it real-time?", "Does it support all
  major platforms?", "How does it handle X?") **do** count when they
  identify a specific capability, limitation, or risk area of the
  **named competitor** — they surface strengths/weaknesses through
  dialogue. Only pure logistical asks ("what's the link?", "when is the
  meeting?") are excluded.
- A user who adds an observation about a strength (e.g. praises a
  specific capability), proposes a weakness (e.g. identifies a concrete
  limitation or risk), or substantively compares the competitor to the
  own product counts. Short-form confirmations ("exactly", "+1",
  emoji-only) do NOT count on their own.

**Hard exclusions (common false positives):**

- A turn that discusses **the own product's** features, roadmap,
  differentiation, "competitive analysis" section, or how the own
  product compares favourably does NOT count — even if it uses the word
  "competitor" or "competitive". The subject of the turn must be a
  **named competitor**, not X itself. A turn whose only reference to
  "competitors" is a request to elaborate on how X's own feature set
  differs from the market does NOT count; only turns that name a
  specific competitor and discuss that competitor's own traits do.
- A turn that shares a general industry article, blog post, tutorial,
  library, framework, or research resource with no commentary about a
  specific named competitor's strengths or weaknesses does NOT count,
  even if the link lives in a competitor-aware channel.
- A turn that mentions "competitor analysis" generically in planning
  (e.g. proposing to *add* a competitor-analysis section) without
  naming or characterising a specific competitor does NOT count.
- A turn about a different product family / codename found in the same
  bundle but belonging to a different product (see Step 3 grounding)
  does NOT count — scope the walk to channels of the target product
  and its confirmed aliases only. Channels that belong to other
  products that happen to be bundled in the same product file must be
  excluded entirely.
- Users whose only contribution is a logistical question ("what's the
  link?"), a pure acknowledgement, sharing a demo URL without analysis,
  or sharing a non-competitor reference link do NOT count.
- Exclude bot/system accounts (whatever admin/bot id the export uses)
  and users whose only mention is being `@`-tagged by somebody else.
- Resolve each user ID through the directory and de-duplicate while
  preserving first-seen order across all competitor discussions.

**Attribute each included user to a specific named competitor.** Before
finalising the list, for every candidate user record which competitor
name their qualifying turn discussed and quote the relevant phrase. If
you cannot cite a named-competitor-specific phrase from that user's
own turn, drop them.

**Per-user audit (do this before writing the answer).** For every
candidate user on the competitor-insights list, open their actual own
turn and confirm **all three** of the following. Drop any user who
fails even one:

1. *Subject check*: the turn's grammatical subject is a named
   competitor product of X (e.g. "`<CompetitorName>` requires ...",
   "`<CompetitorName>` uses ..."), not X itself and not an unspecified
   "competitor" / "the competition" / "they" whose antecedent is
   really X.
2. *Content check*: the turn says something specific about that
   competitor — a feature, limitation, pricing/adoption consideration,
   integration constraint, or probing comparison question about one
   of those attributes. Vague praise/dismissal ("sounds great",
   "interesting", "not sure") fails.
3. *Role check*: the user is not the channel-admin / bot account that
   only reports membership/joins, and the turn is not an
   `@`-mention-only message or a resource-link drop with no commentary
   about a named competitor. A link share with a phrase like "great
   resource for the technology behind **our** product" is an
   own-product turn; drop it. A turn whose entire competitor content
   is a request to "elaborate on how our product differs" is an
   own-product turn; drop it. A turn whose only commentary is pure
   agreement ("agreed", "+1", emoji) fails the content check.

Users whose only turn is a share of a competitor's **demo URL** (just
the link + a product-name label, no analysis) also fail the content
check and must be dropped from the insights list; such a share is
answer evidence for a "demo URL" question, not a "who provided
insights" question.

**Size sanity check.** If your candidate set is noticeably larger
than the number of *substantive* competitor turns you can actually
quote per user, you have admitted users whose turn is only an
acknowledgement, a logistical/probing question with no competitor
content, or an own-product turn. Re-run the audit per user and drop
whichever cases fail any of the three gates.

Questions about **X itself** apply the inverse filter: discard competitor
evidence.

### Step 8 — Extract other entity types

- **Demo / reference URLs**: pull from **both** the product's `urls`
  catalog **and** the body text of chat messages / thread replies
  (regex `https?://[^\s)>\]]+`). For "demo URLs shared by team members"
  the chat body is the primary source — the catalog is a backup and
  may list links no team member ever actually posted. De-duplicate by
  URL. Apply the competitor/own-product filter from Step 7.

  **For "shared by team members" phrasing, require evidence of an
  actual share.** A URL belongs in the answer only if there is at
  least one slack / meeting-chat / meeting-transcript / PR-comment
  message by a human user (not the admin/bot account) whose body text
  contains that URL verbatim. A URL that appears only in the `urls`
  catalog, with no chat message quoting it, does **not** qualify as
  "shared". Walk the chat text with a URL regex and intersect with
  the catalog only to filter, not to inflate.

  For a "demo" filter, prefer URLs whose body or catalog description
  explicitly labels them as a demo (path contains `/demo`, description
  says "demo", etc.). Exclude generic reference links (industry
  articles, library homepages, blog posts) even when a team member
  shared them — those are not demos.
- **Dates**: prefer the artifact's own date field; fall back to message
  timestamps.
- **Names**: resolve to IDs via the directory before returning. Names in
  the dataset may repeat (multiple employees sharing a first+last name):
  prefer the ID that already appears as `userId` / `author` /
  `participants` in the same artifact context before falling back to a
  directory name search.

### Step 9 — Validate and de-duplicate

- All employee IDs must match the directory's pattern (e.g. `eid_...`) and
  resolve to a real entry when a directory is available.
- All URLs must be syntactically well-formed.
- De-duplicate while preserving first-seen order.
- For list answers, keep the list even when it has one element.

---

## Output Contract

### Final JSON file (strict)

Write the saved answer file in exactly this shape (keys follow the
question file's own keys, e.g. `q1`, `q2`, ...):

```json
{
  "q1": {"answer": ["..."], "tokens": 12345},
  "q2": {"answer": ["..."], "tokens": 12345}
}
```

- `answer` is ALWAYS a JSON list, even for a single item.
- `tokens` is an integer approximation of the tokens consumed for that
  question. If an exact count is unavailable, report your best estimate as
  an integer; never omit the field.

Do not add extra top-level keys unless the user's prompt asks for them.

### Internal evidence (kept out of the saved file)

Maintain, but do not write into `/root/answer.json`:

```json
{
  "target_product": "<name>",
  "aliases": ["<codename>", "..."],
  "anchors": [{"question": "q1", "artifact_id": "...", "link": "..."}],
  "evidence": [
    {
      "question": "q1",
      "employee_id": "eid_xxx",
      "role": "key_reviewer",
      "artifact_type": "document|meeting_transcript|slack_message|pr|url",
      "artifact_id": "<id>",
      "snippet": "<short quoted support>"
    }
  ]
}
```

Use this evidence map when writing a short justification message to the
user after the file is saved.

### Recommendation tag per question

Internally tag each question with one of:

- `USE_EVIDENCE` — evidence sufficient and product-grounded.
- `NEED_MORE_SEARCH` — expand to PRs, slack replies, other meetings.
- `AMBIGUOUS` — conflicting product signals or multiple equally valid
  candidates.

---

## Common Failure Modes This Skill Prevents

1. **Treating an internal codename as a distractor.** Codenames must be
   resolved from the data (Step 1); do not reject a candidate just because
   it uses a codename.
2. **Cross-product leakage.** Two-signal grounding (Step 3) prevents
   picking a different product's "same-type" artifact.
3. **Attendees treated as reviewers.** Step 6 requires attributable
   feedback (and prioritizes explicit `feedback` / `reviewers` fields).
   When the document's `feedback` is a plain-text bullet list, the
   reviewers are the transcript speakers whose turns each bullet traces
   back to — not every meeting participant, and not the author who wrote
   the bullets down. The reviewer set for a version is **bounded by the
   bullet count** of that version's feedback: each bullet must be cited
   to a specific source turn; speakers whose turns are not the direct
   source of any bullet are excluded. "All attendees gave substantive
   feedback" is not a valid attribution.
4. **Union-on-every-version by default.** When an artifact has multiple
   versions, each may have its own review meeting. Step 4 **only**
   unions across versions when the question explicitly asks for
   cross-version history ("all versions", "every reviewer"). A
   singular-definite phrasing ("the X", "authors and reviewers of X")
   defaults to the single most-polished version (`latest_` / `final_`
   / most-recent date); unioning every earlier draft's reviewer set
   onto the answer is a frequent over-inclusion failure.
5. **Ignoring ThreadReplies — or stopping when they are empty.** "Who
   provided insights ..." questions typically require scanning nested
   replies. When `ThreadReplies` is empty or absent, the discussion is
   almost certainly carried as flat sibling top-level messages in the
   same channel: sort the channel by timestamp and walk forward from
   the OP to collect every author whose message continues the same
   competitor/topic conversation (Step 6 Tier 3, Step 7).
6. **Mixing competitor and own-product scope.** Step 7 separates them.
   For "insights on strengths/weaknesses of competitors", every
   included user must survive the three-gate per-user audit at the end
   of Step 7: the turn's subject is a **named competitor**, the turn
   says something specific about that competitor (not vague
   agreement), and the user is not the admin/bot or a plain
   link-sharer with no commentary about the competitor. "Elaborate on
   how our product differs" and "add a competitive-analysis section"
   are own-product turns and fail the audit; sharing a competitor's
   demo URL with no analysis is a URL share, not an insight.
6a. **Walking channels of a co-bundled foreign product.** A single
   product bundle may contain channels/meetings belonging to a different
   product. Step 3 rejects those — exclude their messages entirely from
   Step 6 and Step 7 walks.
7. **Wrong version.** Step 4 enforces `latest` / `final` / most-recent for
   version-specific questions, and union for whole-artifact questions.
8. **Dropping the author from an "authors and reviewers" question.** Step
   6 keeps the author when the question asks for both roles.
9. **Treating the URL catalog as "shared".** The `urls` catalog is a
   backup; a catalog entry is not evidence that a team member shared
   that URL. For "shared by team members" URL questions, require a
   chat (or meeting-chat / transcript / PR-comment) turn by a human
   author whose body text contains the URL verbatim. Also exclude
   non-demo reference links (industry articles, library homepages,
   blog posts) from "demo URL" answers.
10. **Schema mismatch.** The Output Contract requires list-valued
    `answer` and an integer `tokens` field per question.

---

## Minimal Working Example (shape only — fill from the data in this run)

```json
{
  "q1": {"answer": ["eid_xxxx", "eid_yyyy"], "tokens": 3200},
  "q2": {"answer": ["eid_zzzz"],             "tokens": 1800},
  "q3": {"answer": ["https://example.com/demo"], "tokens": 1500}
}
```

This is a schema illustration only; the actual IDs, URLs and counts must
come from the real dataset for the current run.

---

## Supporting Scripts

A generic exploration helper is provided under `scripts/` to help the
subagent survey a dataset quickly without pulling large files into
context. See `scripts/README.md` and `scripts/explore_dataset.py`.

The helpers:

- do not embed answers to any specific question;
- do not know about any particular product, codename, or employee;
- only summarize structure and run keyword scans.

They are optional — the Core Procedure above is the contract.
