### output-artifact-finalization-gate | workflow | ensure required answer file is written and schema-validated before terminating
- anchor: (none yet)
- appeared_in: iter_0
- description: The executor completes retrieval/reasoning but fails to persist the required deliverable artifact, so the grader has nothing to evaluate. This manifests as an empty output inventory and termination without any file-write action. The core miss is not having an enforceable end-of-run checkpoint that (1) writes the exact required path (e.g., `/root/answer.json`), (2) conforms to the required schema (often dict keyed by q1..qN), and (3) is verified via read-back.
- latest_executor_action: Before ending the turn, run an explicit completion gate: serialize all answers to the exact required output path; immediately re-open the file and validate (a) file exists at the required path, (b) JSON parses, (c) top-level keys cover all required questions, (d) each value matches the expected object structure (e.g., `{ "answer": [...], "tokens": <int> }`), including “answer is always a list”, and (e) no placeholder/empty values remain unless the task explicitly permits. If any check fails, fix and re-verify; do not terminate until the gate passes.
- remedy_log:
  - iter_0 | diagnosis: rollout ended with no output artifact; missing `/root/answer.json` and no final schema/path verification step
            | patch: (none yet)
