### required-artifact-answers-json | workflow | ensure mandatory /root/answers.json is written and validated before termination
- anchor: plan-package-outputs
- appeared_in: iter_0, iter_1
- description: The executor can complete all reasoning but still fail the task by ending the run without producing the required output artifact. The grader/verifier expects a mandatory JSON file at a fixed path (commonly `/root/answers.json`) with an exact schema (top-level keys like `q1_answer`, `q2_answer`, `q3_answer`, `q4_answer`). A recurring failure mode is “analysis-only” completion: the agent terminates (`end_turn`) without writing the file, or writes it but does not read-back/parse-verify the path + JSON validity + required key set.
- latest_executor_action: Treat required deliverables as hard constraints. Before terminating: (1) extract the exact required path and key set from the prompt; (2) write `/root/answers.json` (not stdout) with exactly those keys; (3) immediately re-open and JSON-parse it; (4) assert no missing keys (and preferably no extra keys if the verifier is strict); (5) confirm the file exists at the exact absolute path; only then `end_turn`.
- remedy_log:
  - iter_0 | diagnosis: agent terminated without writing required /root/answers.json; output inventory empty
            | patch: (pending) add a pre-exit required-artifact checklist rule and an explicit “write + read-back verify” step
  - iter_1 | diagnosis: run ended (end_turn) with `/root/answers.json` missing or not in required schema; skill already contained “do not terminate until deliverables are written” but was not followed
            | patch: (pending) reinforce as a hard stop: termination is forbidden until write+read-back verification passes; align anchor to existing L2 section “Plan & Package Outputs” and pointer to references/required-artifacts-answers-json.md
