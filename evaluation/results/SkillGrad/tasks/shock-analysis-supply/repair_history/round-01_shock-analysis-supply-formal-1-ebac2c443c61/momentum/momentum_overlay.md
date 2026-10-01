### [shock-analysis-supply] run aborted by AuthenticationError (401: key not enabled)
- signal: failure
- pattern: infra-authentication-blocker
- anchor: (none)
- gap: The attempt never reaches any spreadsheet reading/writing logic because the environment/provider rejects the request: `AuthenticationError("Error code: 401 - ... 'this key is not enabled' ...")`.
- proposed_change: Add an L2 workflow preflight step (or harness-level check) to detect credential/configuration failures (401/403, "key not enabled") and fail fast with an explicit "environment blocked" status plus instructions to supply/enable a valid key or switch to a non-authenticated local execution path.

## WORKFLOW-THEMES

- (none this iteration)
