---
name: skilltta-task-guidance
description: Task-specific operational guidance synthesized at test time from retrieved training examples.
---

# SKILL.md

## When to use
Use this skill when the agent must answer a set of natural-language questions grounded in a local enterprise data corpus and emit a strictly-formatted JSON answer file. The binding contract requires:
- Reading questions from a plain-text file that enumerates question keys and their prompts.
- Searching/retrieving over files under a data directory (mixed formats are likely: text, PDFs, CSVs, JSON, spreadsheets, emails, etc.).
- Writing a single JSON file at the exact required path whose top-level keys match the question keys, each mapping to an object with `answer` and `tokens` fields.
- Every `answer` value must be a **list**, even when there is only one item.
- A token-usage figure must be logged per question.

Before acting, gather:
- The exact question keys, wording, and any constraints (e.g., "list all", "which one") in the questions file.
- A directory listing of the data folder and file types present.
- Whether questions require structured lookup (IDs, counts) vs. semantic retrieval (descriptions, relationships).
- How your LLM calls report token usage so you can attribute tokens per question.

## Possible Failure Modes
- Returning a scalar (string/int) instead of a one-element list for single-answer questions — violates the format contract.
- Using different top-level keys than those in `question.txt` (e.g., renaming `q1` → `question_1`, or dropping the `qN` prefix).
- Omitting the `tokens` field, putting it only at the top level, or logging total tokens instead of per-question tokens.
- Writing to a path other than `/root/answer.json`, or writing pretty-printed but not valid JSON (trailing commas, Python `True`/`None`).
- Answering from prior knowledge rather than the provided corpus; hallucinating names/IDs not present in files.
- Ignoring file formats: failing to parse PDFs, XLSX, or nested JSON; only grepping plaintext and missing hits.
- Truncated retrieval: reading only the first N files or first N bytes and missing the ground-truth passage.
- Deduplication/casing errors when the answer is a list (duplicate entries, inconsistent capitalization/whitespace).
- Non-JSON-serializable values (sets, numpy types, Counter, Path) causing `json.dump` to fail silently or with an unhandled exception.
- Overwriting `/root/answer.json` partially on failure, leaving an invalid file.

## Possible procedures
1. **Inventory phase**
   - `ls -R /root/DATA` and classify by extension. Pick appropriate loaders (`pdfplumber`/`pypdf`, `pandas` for csv/xlsx, `json`, plain read for txt/md/eml).
   - Read `/root/question.txt` and parse into an ordered mapping `{qid: question_text}`. Preserve the original qids verbatim.

2. **Indexing / retrieval strategy**
   - For small corpora: load all text into memory and do keyword + regex search per question.
   - For larger corpora: build a lightweight index (e.g., BM25 or embedding + cosine) over chunks with source metadata.
   - Always keep the source file/row reference for each candidate answer so you can verify.

3. **Per-question answering loop**
   - For each qid: retrieve top-k relevant chunks, then ask the LLM (or apply deterministic parsing) to extract the answer strictly from those chunks.
   - Track token usage for that call (prompt + completion) and store it alongside the answer.
   - Normalize the answer into a Python `list`. If the question implies a set (names/ids/items), dedupe while preserving order.

4. **Assembly and write**
   - Build `results = {qid: {"answer": [...], "tokens": <int-or-str>} for qid in questions}`.
   - Serialize with `json.dump(results, f, ensure_ascii=False, indent=2)` to `/root/answer.json`.
   - Re-open and `json.load` the file to confirm it round-trips.

5. **Recovery checks**
   - If a question yields no retrieval hits, broaden the search (synonyms, stemming, scan all files) before returning an empty list.
   - If the LLM returns a scalar, wrap it: `answer if isinstance(answer, list) else [answer]`.
   - If token accounting is unavailable for a step, record a best-effort estimate or `0`, but never omit the key.

## Verification Checklist
- [ ] `/root/answer.json` exists and is valid JSON (loads via `json.load`).
- [ ] Top-level keys exactly match the qids from `/root/question.txt` (same casing, no additions or omissions).
- [ ] Every value is an object with exactly the keys `answer` and `tokens`.
- [ ] Every `answer` field is a `list` (length ≥ 1 when an answer exists; length-1 list for single-item answers).
- [ ] List entries are the correct type (strings for names/ids) with no duplicates and cleaned whitespace.
- [ ] `tokens` is populated per question (not only aggregated at the top level).
- [ ] Answers are grounded in files under `/root/DATA` (spot-check by re-locating each answer in the source).
- [ ] No values from retrieved/example tasks were copied; content comes only from the target corpus.
- [ ] Unrelated files under `/root` are untouched; only `/root/answer.json` was created/overwritten.
- [ ] On any exception during answering, the final file was still written with best-effort results rather than left partial or missing.
