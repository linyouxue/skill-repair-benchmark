### write-required-output-artifacts | workflow | executor ends without writing required /app/output/*.json deliverables
- anchor: (none yet)
- appeared_in: iter_0
- description: The executor terminates the run without materializing any of the required output files, yielding an empty output inventory ([]). This is a procedural omission at the finalization stage: even if computations were performed, the required contract is to write specific JSON files (e.g., q01.json … q05.json) under /app/output/ before ending. The failure is externally observable by the verifier as “missing artifacts,” independent of the correctness of any intermediate reasoning.
- latest_executor_action: Before ending any run, enumerate the required deliverables and deterministically write each one to the exact required path under /app/output/ with the specified filename(s). Then verify (1) each file exists, (2) JSON parses, (3) schema/keys match spec, and (4) any formatting constraints (rounding, sorting, null handling) are satisfied; only then terminate.
- remedy_log:
  - iter_0 | diagnosis: output inventory is empty; executor terminated end_turn without writing any /app/output JSON deliverables
            | patch: (none yet—recorded for patcher to add an explicit “write artifacts + verify” completion protocol to the skill)
