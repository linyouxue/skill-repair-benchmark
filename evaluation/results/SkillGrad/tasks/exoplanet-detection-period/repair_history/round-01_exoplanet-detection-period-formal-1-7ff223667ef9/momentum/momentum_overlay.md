### [exoplanet-detection-period] missing required `/root/period.txt` output artifact
- signal: failure
- pattern: output-finalization-write-required-artifact
- anchor: (none)
- gap: Agent terminated (“termination_reason: end_turn”) with “Output inventory: []”; it never wrote the computed period to `/root/period.txt` in the required format (single numeric value rounded to 5 decimals).
- proposed_change: Add a mandatory end-of-run completion checklist step in workflow guidance (L2) for all exoplanet period tasks: write `/root/period.txt` with exactly one float (rounded to 5 decimals, no surrounding text) and then read it back to confirm it exists and parses.

## WORKFLOW-THEMES

- (none this iteration)
