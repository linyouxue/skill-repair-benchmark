# Secure JSON Endpoint Gating Against Config-Bypass (Jackson-Based Services)

## Purpose
Provide a reusable workflow to fix vulnerabilities where a JSON request can bypass a server-side security setting (for example, JavaScript execution disabled) due to how the endpoint deserializes or injects configuration. The goal is to (1) identify the exact request parsing path, (2) enforce the gate at the correct control point, and (3) prove both exploit blocking and non-regression with an executable reproduction.

## When to Use
Use this skill when a service accepts JSON (often via Jackson) and a request can enable or access a restricted feature by smuggling or overriding config in the request (for example, via injected fields, duplicate keys, special property names, or server-side injectable values). Do not use this skill for general Jackson hardening, unrelated dependency upgrades, or vulnerabilities that are not about request-time bypass of a feature gate.

## Procedure
- 1) Confirm scope and entrypoint (discovery before edits)
- Locate the exact endpoint/controller/handler that accepts the JSON payload and identify the DTO/request class used for deserialization.
- Trace the dataflow from "raw request body" to "feature use" (for example, where JavaScript would be compiled/executed) and identify the intended gate (config flag, runtime setting, allowlist).
- Checkpoint: you can name the method(s) that (a) deserialize the request and (b) decide whether the restricted feature is allowed.
- 2) Build a minimal reproduction anchored to the real code path (baseline)
- Prefer an automated test (unit/integration) that calls the endpoint handler or the lowest method that still performs the same parsing + gate decision.
- Add two cases:
- Restricted feature globally disabled: the request must be rejected (or the feature must remain off).
- Restricted feature globally enabled: a legitimate request must succeed.
- If the exploit involves a special JSON structure (duplicate keys, empty key name, injected config object), encode that structure in the test payload exactly.
- Execution anchor: run the reproduction before changing code and record the observable result (failing assertion, HTTP status/body, or exception) that demonstrates the bypass.
- 3) Identify the bypass primitive and choose the narrowest fix point
- Determine whether the bypass happens due to:
- Deserialization into the wrong type / polymorphism,
- Request fields overriding server config,
- Server-side injectable values being overwritten by request input,
- Parser behavior (duplicate keys, special property names) changing semantics.
- Decision point: enforce the gate where it cannot be overridden by request JSON:
- If the endpoint should never accept a per-request override, strip/ignore the request field and use only server config.
- If a per-request field is allowed only when globally enabled, explicitly compute "effectiveAllowed = globalSetting AND requestWantsIt" and reject otherwise.
- If injection is involved, ensure server-derived values cannot be supplied by untrusted input in this code path (prefer explicit wiring over implicit injection).
- 4) Implement the fix with minimal surface area and explicit semantics
- Change the endpoint/handler/request-binding so that untrusted JSON cannot flip the restricted feature from disallowed to allowed.
- Keep changes localized to the request parsing / config composition layer for that endpoint.
- Add or update tests to assert:
- The bypass payload is rejected when globally disabled.
- Legitimate payload succeeds when globally enabled.
- Checkpoint: no unrelated refactors; no dependency/build changes unless a failing build/test proves they are required for verification.
- 5) Verify post-fix behavior (same reproduction, plus one non-regression)
- Re-run the exact baseline reproduction:
- The bypass case must now fail deterministically at the gate (clear error or status).
- The legitimate enabled case must still pass.
- If service-level execution is available, add one end-to-end call (for example, curl against a local instance) mirroring the test payloads.
- Execution anchor: capture the post-fix test output (or HTTP response) as evidence before concluding the issue is fixed.
- 6) Bounded fallback if tooling/environment blocks full reproduction
- If you cannot run the full service: run the narrowest test that still executes the same deserialization and gate decision (for example, instantiate the same ObjectMapper/config and call the handler method directly).
- If build issues appear: do not change dependency versions by default. First prove necessity by isolating the failure to a missing artifact/tooling issue and prefer the smallest, verifier-compatible adjustment. If you must touch build files, keep it minimal and directly justified by a failing build log tied to running the reproduction.

## Constraints / Pitfalls
- Do not claim "exploit blocked" or "no regression" without running the same pre/post reproduction anchored to the actual endpoint parsing path and gate decision; reasoning-only fixes are not acceptable.
- Do not introduce broad Jackson hardening, dependency upgrades, or build-file edits unless they are required to execute the reproduction; unrelated changes increase verifier divergence and can mask whether the gate is actually enforced.