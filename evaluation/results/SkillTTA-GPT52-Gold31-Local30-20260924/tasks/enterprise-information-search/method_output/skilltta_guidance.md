# SKILL.md

## When to use
Use this skill when you must answer *multiple* retrieval questions over a local “enterprise” dataset and write a single JSON file containing one entry per question. The contract typically includes:
- A fixed data directory (e.g., an on-disk folder with heterogeneous files).
- A question file containing multiple question keys (e.g., `q1`, `q2`, …) and their text.
- A required output path (must write a JSON file) and a strict schema per question: `{ "answer": ..., "tokens": ... }`.
- A rule that answers must be lists (even for singletons).

Before acting, gather evidence by:
- Inspecting the question file structure (how questions are keyed; whether it’s JSON, text, YAML-like, etc.).
- Listing the dataset directory contents and identifying file types (CSV/JSON/PDF/logs/emails/db dumps).
- Determining how “token consumption” should be measured/recorded in your runtime (or approximated consistently if no tokenizer is available).

## Possible Failure Modes
- **Wrong output schema**: writing a plain dict of answers instead of nested objects with `"answer"` and `"tokens"` per question, or missing required keys.
- **Not using list answers**: returning a scalar string/id when the contract requires a list even for one item.
- **Overwriting/partial writes**: producing invalid JSON, truncating the output, or failing to write to the exact required path.
- **Mis-parsing the questions file**: assuming JSON when it’s line-based, or losing question IDs/ordering.
- **Ambiguous retrieval without evidence**: selecting a plausible value without tracing it back to the dataset, leading to unverifiable results.
- **Dropping “no result” cases**: omitting a question key entirely rather than providing an explicit empty list (or another contract-compliant null representation).
- **Token logging mistakes**: logging a single global token count instead of per-question, or putting non-serializable objects in `"tokens"`.
- **Environment/network leakage**: attempting external calls (e.g., web/API requests) instead of using the local dataset, which can fail in sandboxed environments.
- **Type drift in JSON**: storing sets/Counter objects or other non-JSON-serializable structures (must convert to lists/ints/strings).

## Possible procedures
1. **Inventory inputs**
   - Read the question file raw first; infer its format safely (try JSON parse; if fails, treat as text and extract `qN` blocks with robust regex/line parsing).
   - List `/root/DATA` recursively; note filenames, extensions, and sizes to choose parsers.

2. **Normalize questions into an internal structure**
   - Build a dict like `{qid: question_text}`.
   - Keep original `qid` strings exactly; never renumber or rename keys.

3. **Plan retrieval per question**
   - For each question, decide the best search strategy:
     - Keyword/regex search across text-like files.
     - Structured query over CSV/JSON tables (load with pandas/json module).
     - Full-text scan for logs (stream line-by-line for large files).
   - Maintain “provenance notes” during retrieval (file name + matching line/record) to resolve conflicts.

4. **Extract candidate answers**
   - Prefer deterministic extraction: exact matches, unique IDs, exact field values.
   - If multiple matches are valid, return all of them as a list.
   - If exactly one match, still wrap it in a one-element list.
   - If none found, return an empty list (unless the contract specifies another representation).

5. **Compute token usage per question**
   - If you have a tokenizer available, compute tokens from the model input/output relevant to that question.
   - If not, use a consistent approximation method (e.g., character-based or whitespace-based) and document it internally; ensure `"tokens"` is JSON-serializable (commonly a string or integer). Keep it per question as required.

6. **Assemble the output object**
   - For each `qid`, create:
     - `"answer"`: a list (items should be strings/ids as appropriate).
     - `"tokens"`: per-question token count in the required primitive type.
   - Ensure every question key from the input appears exactly once in the output.

7. **Write atomically and safely**
   - Serialize with `json.dump(..., ensure_ascii=False)` and optionally indentation for readability.
   - Write to a temp file then rename to the required path to avoid partial writes.

8. **Recovery / ambiguity handling**
   - If conflicting sources provide different answers, re-check with stricter filters (e.g., exact field name match, newest timestamp, unique constraints).
   - If still ambiguous, return all plausible items in the list (unless the question implies a single authoritative item—then apply a consistent tie-break rule grounded in the data, not guesswork).

## Verification Checklist
- [ ] Read all questions and preserved every original question key (no missing/extra keys).
- [ ] Output file exists at the required absolute path and is valid JSON (loadable via Python `json.load`).
- [ ] For each question: output value is an object with exactly (at least) `"answer"` and `"tokens"`.
- [ ] `"answer"` is always a **list**, including singleton answers (length 1) and “no result” answers (empty list, if allowed).
- [ ] `"tokens"` is present **per question** and is JSON-serializable (string/int), not a complex object.
- [ ] No reliance on external network resources; retrieval is performed solely from the local dataset directory.
- [ ] No copying of concrete details from unrelated retrieved examples; solution logic is driven by the current dataset and questions.
- [ ] Unrelated files/state are not modified; only the required output file (and optional temporary file during atomic write) is created/changed.
- [ ] Spot-check a few answers by tracing them back to source files/records to confirm correctness and avoid hallucinated values.
