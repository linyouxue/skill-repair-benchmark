# Jackson Empty-Key Deserialization Patch Workflow

## Purpose
Guide remediation of Java CVEs where a crafted JSON body uses an empty key (`""`) or similar structural trick to drive Jackson into a sensitive sink (field injection, any-setter, custom deserializer) before application code validates the resulting object. The workflow enforces sink enumeration, remediation choice, and reproducer-based verification rather than relying on a single annotation fix.

## When to Use
Use when a CVE or report implicates Jackson deserialization and mentions empty keys, `@JacksonInject`, `useInput`, `@JsonAnySetter`, or value override via JSON structure. Do not use for polymorphic-type (`@JsonTypeInfo`) RCE, duplicate-key WAF bypass, or pure post-deserialization validation bugs; those need different vectors.

## Procedure
- Identify the sink class and field named by the CVE or reproducer. Record the fully qualified type (e.g., `com.example.FooConfig`) and the field or setter under attack.
- Enumerate all candidate sinks across the repository for that type: grep for `@JacksonInject`, `@JsonAnySetter`, `@JsonCreator`, `@JsonSetter("")`, and `StdDeserializer`/`JsonDeserializer` subclasses that reference the type. Produce a file:line list; do not assume a single site.
- Choose remediation per sink, in this order of preference: (1) `@JacksonInject(useInput = OptBoolean.FALSE)` on injected fields so JSON cannot override the server-provided value; (2) override or guard the `@JsonAnySetter` / custom deserializer to reject empty or unexpected keys; (3) at the `ObjectMapper` level, enable `DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES` and `JsonParser.Feature.STRICT_DUPLICATE_DETECTION`, and configure explicit empty-key rejection in the request filter; (4) re-assert the runtime enabled/authorization check at the execution site (defense in depth).
- Verify with a reproducer: construct a JSON body containing the empty-key payload against the real endpoint or a unit test invoking the mapper. Confirm the exploit path triggers before the patch and is blocked after. If the annotation-level fix leaves the reproducer succeeding, fall back to step 3 remediations and re-run.

## Constraints / Pitfalls
- Do not stop after patching one annotation site; the same config type may be injected or any-set in multiple modules, and partial coverage leaves the CVE exploitable.
- Do not rely on post-`readValue` object inspection to detect empty keys; the key is gone by then. Verification must drive the raw JSON through the real deserialization path and observe sink behavior, not the resulting object.