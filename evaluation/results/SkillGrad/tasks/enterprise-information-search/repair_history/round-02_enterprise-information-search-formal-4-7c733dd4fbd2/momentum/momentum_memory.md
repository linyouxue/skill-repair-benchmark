### output-artifact-finalization-gate | workflow | ensure required answer file is written and schema-validated before terminating
- anchor: finalize-required-write-root-answer-json-validate-before-terminating
- appeared_in: iter_0, iter_2
- description: The executor completes retrieval/reasoning but fails to persist the required deliverable artifact, so the grader has nothing to evaluate. This manifests as an empty output inventory and termination without any file-write action. The core miss is not having an enforceable end-of-run checkpoint that (1) writes the exact required path (e.g., `/root/answer.json`), (2) conforms to the required schema (often dict keyed by q1..qN), and (3) is verified via read-back.

  Iter_2 confirms this can happen even when an L2 rule exists: the run shows 0 skill invocations and the agent terminates before executing any finalize/write + read-back validation step.
- latest_executor_action: Treat finalization as a hard completion gate. Immediately before ending the run: (1) read `/root/question.txt` to enumerate required q-keys, (2) build a top-level dict with exactly those keys, each mapping to an object that includes `answer` (always a list) and `tokens` (int), plus any harness-required extra fields, (3) write to the exact required output path (default `/root/answer.json` unless overridden), then (4) read it back, JSON-parse, and validate schema + key coverage. If any check fails (file missing/wrong path, parse error, missing keys, wrong types), fix, re-write, and re-validate; do not terminate until the gate passes.
- remedy_log:
  - iter_0 | diagnosis: rollout ended with no output artifact; missing `/root/answer.json` and no final schema/path verification step
            | patch: (none yet)
  - iter_2 | diagnosis: agent ended run without creating required `/root/answer.json`; termination occurred before any "finalize/write + read-back validation" action; trace indicates 0 skill invocations despite existing L2 finalize rule
            | patch: set anchor to existing L2 finalize section slug and strengthen rule to be treated as a hard stop-before-terminate gate; recommend invoking references/finalize_answer_json.md when multi-question or prior file-missing failure
