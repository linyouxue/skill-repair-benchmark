# QA File Loop To Verifier-Aligned answer.json

## Purpose
Produce verifier-aligned answers for multiple questions stored in a local question file by looping over discovered question ids, answering each using minimal necessary evidence lookup, and writing a single JSON artifact to the required output path with a schema-validated structure.

## When to Use
Use when a task requires: (a) reading one local question file (commonly /root/question.txt), (b) generating answers for multiple keyed questions, and (c) writing a machine-checked JSON file (commonly /root/answer.json). Do not use for single-question, conversational answers that do not require an on-disk JSON artifact.

## Procedure
- Step 1: Discover inputs and required outputs (no assumptions)
- Confirm the question file path from the task instructions; if not provided, search minimally (current directory, then /root) for a likely question file and stop to ask if ambiguous.
- Open and parse the question file to extract a stable list of (question_id, question_text).
- Decision point: If ids are missing/ambiguous (for example, free text without clear separators), stop and request clarification or define a deterministic parsing rule and document it in the output.
- Step 2: For each question id, answer with bounded, evidence-first lookup
- For each (question_id, question_text):
- Identify what must be looked up vs. derived (names, ids, dates, counts, file contents).
- Perform targeted discovery in the local environment (list relevant directories, grep/search for exact identifiers) before opening large artifacts.
- Extract only what is needed to answer; keep a short internal evidence note (file name + line/record pointer) so you can re-check quickly.
- Decision point: If multiple plausible answers remain, choose the one best supported by direct artifact text; otherwise mark the answer as ambiguous in the answer field rather than guessing.
- Step 3: Populate consumed_tokens with a contract-safe rule (no environment mutation)
- Do not install packages (no pip/apt/venv) solely to compute tokens.
- If the runtime/tooling provides an explicit token-usage metric for the specific question (for example, per-call usage from the platform), record that integer.
- Otherwise, set consumed_tokens to null (or omit only if the task explicitly allows omission). Do not fabricate heuristic estimates and present them as true consumption.
- Step 4: Write /root/answer.json and validate it matches the discovered contract (final checkpoint)
- Build an object mapping each discovered question_id to an object containing:
- answer: the per-question answer (string or JSON-serializable object as required by the task)
- consumed_tokens: integer usage if available, else null per Step 3
- Write the JSON to the exact required output path (commonly /root/answer.json). Do not write to an alternate path.
- Execution anchor (must pass before finishing): reload /root/answer.json and validate:
- File exists and is readable at the required path.
- JSON parses successfully.
- Top-level keys exactly match the discovered question ids (no missing, no extras).
- Each value is an object containing answer and consumed_tokens with acceptable types (answer is JSON-serializable; consumed_tokens is integer or null per Step 3).
- If validation fails, fix the construction and rewrite, then re-validate.

## Constraints / Pitfalls
- Do not mutate the environment to satisfy bookkeeping (no pip/apt installs for token counting). If token usage is not available from the platform, use a null/unknown policy rather than a heuristic number.
- Do not over-scan or load large artifacts by default: start with discovery (directory listing, targeted search) and cap retrieval to what the question requires; if requirements are ambiguous, stop and ask rather than guessing.