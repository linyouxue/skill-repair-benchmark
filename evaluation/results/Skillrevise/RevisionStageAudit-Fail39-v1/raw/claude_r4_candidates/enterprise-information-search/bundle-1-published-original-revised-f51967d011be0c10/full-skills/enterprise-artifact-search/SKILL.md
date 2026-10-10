# Enterprise Artifact Multi-Question Search

## Purpose
Answer a set of enterprise-artifact questions (entity IDs, URLs, dates, names) by discovering the dataset layout, iterating per question, and grounding every emitted value verbatim in a cited artifact under the dataset root.

## When to Use
Use when the task provides a questions file plus a workspace of interlinked artifacts (docs, chats, meetings, PRs, URLs, directories) and requires a JSON answer whose values must be retrieved (not inferred) and traceable to specific artifacts. Also use when the same artifact type (for example "Market Research Report") exists for multiple products and cross-product leakage is a risk.

## Procedure
- Step 1 - Parse questions. Read the task-specified questions file (discover its path from the task prompt; do not assume a fixed name). Build an ordered map {qid: question_text} and print it. For each qid, classify the expected value type (employee_id list, url list, date, name, free text) and the entity scope (product, team, document type).
- Step 2 - Discover dataset. Run a directory listing of the dataset root and sample the top-level keys and nested shape of each JSON/text artifact type before referencing any field. Record the actual field names for people, documents, chats, meetings, PRs, and URLs. Do not use field names from prior tasks until confirmed here.
- Step 3 - Per-question retrieval loop. For each qid: (a) wide-recall candidate artifacts by keyword and scope; (b) filter by at least two independent grounding signals tying each candidate to the question's target scope (container location, explicit name match, channel/meeting series, link path, cross-reference); (c) extract values only from discovered field names; (d) for list answers, prefer explicit structured fields over inferred participants or acknowledgements.
- Step 4 - Evidence map. For every extracted value, record {qid, value, artifact_type, artifact_id, verbatim_snippet}. Reject any value whose exact string (for URLs, IDs) or clearly supporting phrase (for names, dates) is not present in a cited snippet.
- Step 5 - Write and validate. Write the answer JSON to the task-specified output path (discover from the task prompt). Then reload it and assert: keys equal the parsed qids; each scalar or list element is covered by at least one evidence record; value types match the per-qid classification. If any assertion fails, repair before claiming completion.

## Constraints / Pitfalls
- No hard-coded paths, filenames, product names, or field names. Discover them in Step 2; if discovery fails, mark the question AMBIGUOUS rather than guessing.
- Forbid synthesizing URLs, IDs, or dates. If an expected URL or ID is not found verbatim under the dataset root, return an empty list or AMBIGUOUS for that qid; never emit plausible-looking patterns (for example "<name>.com/demo").
- Meeting participant lists alone do not establish reviewer, approver, or contributor roles; require an explicit field or a transcript turn with substantive content.
- When the same document type exists across multiple products or teams, require two independent grounding signals before accepting a candidate; reject first-hit matches that fail this gate.
- Keep the subagent context lean: pass only the parsed question, scope, and discovered field names; do not inline large artifacts.