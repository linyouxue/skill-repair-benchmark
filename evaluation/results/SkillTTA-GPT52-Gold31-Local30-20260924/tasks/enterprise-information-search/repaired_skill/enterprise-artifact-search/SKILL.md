---
name: enterprise-information-search
description: Answer multiple retrieval questions from /root/question.txt over the local enterprise dataset at /root/DATA, writing a single /root/answer.json with per-question {"answer": [...], "tokens": ...}.
---

# Enterprise Information Search Skill

Use this skill when you must:
- read **multiple questions** keyed like `q1`, `q2`, ... from `/root/question.txt`
- retrieve answers **only from local files** under `/root/DATA`
- write a **single JSON file** to `/root/answer.json` where each question key maps to an object:
  - `"answer"`: **always a list** (even for a single item)
  - `"tokens"`: **per-question** token usage (integer or string)

---

## Contract (must follow)

### Inputs
- Dataset directory: `/root/DATA`
- Questions file: `/root/question.txt` (format may be JSON or plain text)

### Output
Write `/root/answer.json` with this shape (every question key must appear exactly once):

```json
{
  "q1": {"answer": ["..."], "tokens": 123},
  "q2": {"answer": [], "tokens": 45}
}
```

Rules:
- If an answer contains multiple items/ids/names, store them all in the list.
- If only one item, still store it as a **one-element list**.
- If nothing is found, store an **empty list**.
- Log token usage **per question** inside each question object (do not use a single global count).

---

## Procedure

### Step 1 — Parse `/root/question.txt` safely
1) Read the file raw.
2) Try parsing as JSON first:
   - a dict like `{ "q1": "...", "q2": "..." }`
   - or a list of objects like `[{"id":"q1","question":"..."}, ...]`
3) If JSON parse fails, treat it as text and extract `qN` blocks with robust parsing, e.g.:
   - lines like `q1: ...`
   - or `q1\n<question text>\nq2\n...`

Normalize into an internal dict:

```python
questions = {"q1": "...", "q2": "..."}
```

Never rename keys.

---

### Step 2 — Inventory the dataset
- Recursively list `/root/DATA`.
- Choose parsers by extension:
  - `.csv/.tsv`: pandas/csv
  - `.json/.jsonl`: json module / streaming for large files
  - `.txt/.md/.log`: line-by-line scan
  - Office/PDF (if present): prefer any provided extracted text; otherwise search metadata/filenames first.

Avoid external/network calls.

---

### Step 3 — Retrieve answers (per question)
For each `(qid, qtext)`:

1) Identify likely entities requested (ids, names, dates, amounts, etc.).
2) Use a deterministic strategy, preferring structured sources:
   - If the question implies a table field (e.g., “employee id for Alice”), search structured directories first.
   - Otherwise, use keyword/regex search across text-like files.
3) When multiple matches are plausible, return **all** items that satisfy the question.
4) Extract exact strings/ids from source records (avoid inventing).

Normalization rules:
- Return `answer_list: list[str]` (or list of primitive JSON types if clearly requested).
- Deduplicate while preserving order.

---

### Step 4 — Compute tokens per question
Record token usage **per question**.

Preferred:
- If a tokenizer is available in the runtime, compute tokens for (question text + minimal retrieved snippets used + produced answer).

Fallback (must be consistent):
- Approximate tokens as `ceil(len(text)/4)` where `text` is the concatenation of:
  - the question text
  - the serialized answer items joined with spaces

Store as an integer (or cast to string if the evaluation environment strictly expects strings).

---

### Step 5 — Write `/root/answer.json` atomically
- Build a dict:

```python
out = {
  qid: {"answer": answer_list, "tokens": token_count}
  for qid in questions
}
```

- Write to a temp file and rename to `/root/answer.json` to avoid partial writes.
- Ensure the JSON is loadable by Python `json.load`.

---

## Common failure modes to avoid
- Writing scalar answers instead of lists.
- Omitting question keys with no results (must include key with `[]`).
- Writing the wrong schema (must be `{qid: {answer, tokens}}`).
- Using a single global token count instead of per-question.
- Guessing answers without evidence from `/root/DATA`.
