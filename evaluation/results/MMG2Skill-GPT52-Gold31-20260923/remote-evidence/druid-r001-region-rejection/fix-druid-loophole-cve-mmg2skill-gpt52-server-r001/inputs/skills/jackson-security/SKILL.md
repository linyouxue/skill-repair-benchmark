---
name: jackson-security
description: Harden Jackson JSON deserialization against config-injection/override
  tricks (including empty-string `""` keys) and ensure JavaScript execution controls
  cannot be enabled from request bodies.
---

## Steps
1. Identify any request-body–deserialized classes involved in JavaScript-based features (e.g., sampler specs / transform filters) that receive security configuration via `@JacksonInject` (notably `JavaScriptConfig`).
2. For every constructor/factory parameter annotated like `@JacksonInject JavaScriptConfig config`, change it to **ignore any JSON-provided value** by using:
   - `@JacksonInject(useInput = OptBoolean.FALSE) JavaScriptConfig config`
   - Add `import com.fasterxml.jackson.annotation.OptBoolean;`
3. Ensure there are no alternative JSON-settable fields/setters that can override the injected `JavaScriptConfig` after construction (search for other `JavaScriptConfig` properties and Jackson annotations).
4. Add a focused deserialization-level test (unit test) that attempts to deserialize a malicious payload containing an empty-string key intended to override the injected config (e.g., `"": {"enabled": true}`) and assert:
   - the injected config value is still used (input override did not occur), and/or
   - deserialization is rejected if that is the intended behavior.
5. Add a companion “legitimate request” test to ensure normal sampler/filter JSON without the injection attempt still deserializes and behaves as expected.
## Expected Result
Malicious JSON containing `""` (or similar) cannot override injected security configuration to enable JavaScript execution; legitimate sampler/spec requests still work.
