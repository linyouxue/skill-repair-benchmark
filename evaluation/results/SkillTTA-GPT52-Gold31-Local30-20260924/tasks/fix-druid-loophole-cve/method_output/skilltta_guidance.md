# SKILL.md

## When to use
Use this skill when you must patch a **server-side code execution / sandbox-bypass** vulnerability caused by **malicious JSON input manipulating JavaScript-related settings** in an Apache Druid-like ingestion/sampler API. The contract typically includes:
- Produce **patch files** in a specific patches directory, **apply** them to a **git checkout** of the source, and **rebuild** with a provided Maven command (often skipping heavy modules and quality gates).
- Ensure the patch blocks **exploit requests** while preserving **legitimate request behavior** (verifier will restart server and run tests).

Before acting, gather evidence by:
- Locating the **request handler** (endpoint/controller) and the **request DTO(s)** used to deserialize the JSON spec.
- Finding where **JavaScript is allowed/disabled** (config flags, feature toggles, “security” settings, or guards around “javascript” filters/transforms).
- Identifying how JSON is deserialized (e.g., Jackson annotations, `Map` fields, `@JsonAnySetter`, “unknown field” handling) and where an **empty key `""`** could alter behavior.

## Possible Failure Modes
- **Patching the wrong layer**: fixing UI/client-side validation or only the sampler endpoint while other ingestion paths accept the same spec.
- **Relying on “unknown field ignore”**: allowing extra JSON keys (including `""`) to be silently accepted and later interpreted via generic maps/any-setters.
- **Over-blocking**: rejecting all JavaScript-related specs even when JavaScript is legitimately permitted by server configuration, causing legitimate requests to fail.
- **Under-blocking**: blocking only the exact shown payload shape instead of the underlying bypass primitive (e.g., empty-string field names anywhere that influences deserialization/feature toggles).
- **Breaking compatibility**: changing JSON schema behavior in a way that rejects common benign extra fields used by clients (be precise: block the exploit vector, not “all unknowns” globally unless safe).
- **Not updating all entry points**: Druid often has multiple ways to submit/validate ingestion specs; missing one allows exploitation to persist.
- **Patch not actually built/deployed**: edits outside the built module set, forgetting to apply patches, or failing Maven module selection.
- **Rebuild succeeds but runtime still vulnerable**: fix placed after the dangerous code path (e.g., JS executed before validation/guard).

## Possible procedures
1. **Reproduce and map the exploit path (safely)**
   - Trace the endpoint receiving the JSON (sampler/ingestion endpoints).
   - Identify the classes used to deserialize `spec`, `dataSchema`, `transformSpec`, and `filter`.
   - Determine where JavaScript code execution is triggered (e.g., a “javascript filter” factory or script engine wrapper).

2. **Identify the bypass primitive**
   - Look for any of:
     - Parsing into `Map<String, Object>` where keys can be `""`.
     - `@JsonAnySetter` collecting unknown properties.
     - Logic like `map.getOrDefault(key, ...)` where `key` could be empty or derived from JSON.
     - Feature toggles read from nested “context”/“config” objects that accept arbitrary keys.
   - Confirm how the presence of an empty key could flip “enabled”/security settings.

3. **Choose a robust mitigation strategy**
   Prefer defenses that eliminate the class of bypass rather than matching a single payload:
   - **Reject empty-string JSON field names** in relevant spec sub-objects (especially around transform/filter configuration).
     - Implement validation after deserialization and before any JS compilation/execution.
     - If you control Jackson configuration locally for this endpoint, consider strict parsing/validation hooks.
   - **Decouple request data from server security configuration**:
     - Ensure server-side “JavaScript enabled?” decision is based only on trusted server config, not request-provided fields.
     - If request can provide an “enabled” flag, treat it as non-authoritative (ignore it) or require it to be consistent with server policy.
   - **Harden deserialization** at the DTO level:
     - For classes representing filter/transform configs, consider disallowing unknown properties *only where safe*, or explicitly validating “extra properties” captured by any-setters.
     - If a generic map must exist, validate keys: non-empty, expected set, and correct types.

4. **Apply the fix at the right choke point**
   - Place validation **before** any script engine / expression compilation is reached.
   - Ensure the validation runs for:
     - sampler endpoint ingestion-spec parsing, and
     - any shared ingestion spec parsing used by other endpoints (if applicable within the built modules).

5. **Patch packaging discipline**
   - Create patch files under the required patches directory using standard unified diff format.
   - Apply patches to the git repo and keep changes minimal and reviewable.
   - Avoid touching unrelated formatting or files outside necessary modules to reduce risk.

6. **Build with the provided Maven invocation**
   - Use the exact flags/module selections required (skip heavy modules like web-console; skip code quality gates as instructed).
   - If compilation fails, iterate by narrowing imports/visibility changes and ensuring changed code belongs to included modules.

7. **Behavioral recovery checks**
   - If legitimate requests start failing, adjust validation to:
     - only reject the exploit primitive (e.g., empty keys / forbidden properties),
     - preserve previously supported benign fields, and
     - keep error handling consistent with existing API patterns (HTTP status + message schema).

## Verification Checklist
- [ ] Patch files exist in the required patches directory, are valid unified diffs, and apply cleanly to the repository.
- [ ] The fix prevents request-provided JSON (including empty-string keys) from enabling/triggering JavaScript execution when server policy disallows it.
- [ ] Validation occurs **before** any JavaScript compilation/execution path.
- [ ] Legitimate sampler/ingestion requests that do not use the bypass still succeed (no blanket rejection of all JavaScript-related configs unless policy dictates).
- [ ] All relevant ingestion-spec entry points in the built modules are protected (not just a single controller method if shared parsers exist).
- [ ] Maven build completes using the required command and module selection; resulting artifacts include the patched classes.
- [ ] No hard-coded values, identifiers, or payload specifics are copied from retrieved examples (use them only as inspiration for input-validation rigor).
- [ ] Unrelated repository state/config is preserved (no accidental edits to build files or unrelated modules).
- [ ] If verifier-like tests fail, collect runtime logs, identify whether failure is “still vulnerable” vs “over-blocking,” and refine validation boundaries accordingly.
