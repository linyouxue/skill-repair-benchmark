# Pattern record (updated)

### infra-authentication-blocker | workflow | task run fails due to invalid/disabled API key causing AuthenticationError
- anchor: (none yet)
- appeared_in: iter_0
- description: The executor never reaches task logic because the run aborts on an upstream authentication failure (e.g., `AuthenticationError("Error code: 401 - ... 'this key is not enabled' ...")`). This is not a skill-application mistake inside spreadsheet logic; it is an environment/credential gate that prevents any attempt, traces, or outputs from being produced.
- latest_executor_action: Detect authentication/credential errors early (401/403, "key not enabled", "invalid api key"). Stop and surface a clear diagnostic stating the run is blocked by credentials/config; do not attempt to proceed with task operations. If the harness allows, request a valid enabled key or switch to an offline/local execution path that does not require the failing provider.
- remedy_log:
  - iter_0 | diagnosis: execution aborted with 401 AuthenticationError "this key is not enabled"
            | patch: record environment blocker; no skill-file anchor available in current xlsx guidance
