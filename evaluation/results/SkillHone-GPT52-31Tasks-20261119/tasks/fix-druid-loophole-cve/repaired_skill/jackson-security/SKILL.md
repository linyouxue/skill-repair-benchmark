---
name: jackson-security
description: Security considerations for Jackson JSON deserialization in Java applications. Covers timing of validation, raw input interception, and common deserialization attack patterns.
---

# Defensive Patch Runbook: Apache Druid (CVE-2021-25646)

This section is a **defensive** runbook for patching older Druid builds where a crafted JSON payload could cause **server-injected configuration** (notably `JavaScriptConfig`) to be overridden during deserialization.

## Goal (defensive)

- Ensure an **invalid/empty selector name** in JSON cannot override the server’s injected `JavaScriptConfig` setting.
- Preserve normal behavior:
  - If the server has JavaScript **enabled**, JS-based features continue to work.
  - If the server has JavaScript **disabled**, JS-based features remain disabled (even under hostile input).

## Where the issue lives (high-level)

Druid uses `@JacksonInject` with a Guice-backed `AnnotationIntrospector` to inject server-side objects into request/segment JSON.

Some Jackson code paths can treat **missing creator-parameter names** as an empty string; with `@JacksonInject` default `useInput` behavior, an empty-name JSON property could be (incorrectly) considered a match and override the injected value.

## Recommended fix (backport-style)

In Druid `0.20.0`, implement a guard in:

- `core/src/main/java/org/apache/druid/guice/GuiceAnnotationIntrospector.java`

Add an override of `findPropertyIgnorals(...)` that **ignores the empty-string property name** (`""`) for members/parameters that do **not** have an explicit `@JsonProperty` name.

Minimal pattern (safe, defensive):

```java
// imports you will likely need:
//   com.fasterxml.jackson.annotation.JsonIgnoreProperties;
//   com.fasterxml.jackson.annotation.JsonProperty;
//   com.fasterxml.jackson.databind.introspect.Annotated;
//   com.fasterxml.jackson.databind.introspect.AnnotatedParameter;

@Override
public JsonIgnoreProperties.Value findPropertyIgnorals(Annotated ac)
{
  if (ac instanceof AnnotatedParameter) {
    final AnnotatedParameter ap = (AnnotatedParameter) ac;
    if (ap.hasAnnotation(JsonProperty.class)) {
      // Keep normal creator-parameter behavior for explicitly named params.
      return JsonIgnoreProperties.Value.empty();
    }
  }

  // Disallow empty-string names as a general rule.
  return JsonIgnoreProperties.Value.forIgnoredProperties("");
}
```

Notes:

- This is intentionally **narrow**: it targets the invalid empty-name case without changing the normal JSON shape for legitimate requests.
- Prefer a backport of the upstream-style fix rather than changing `JavaScriptConfig` semantics.

## Patch / build workflow (for SkillHone-style tasks)

When the task requires a patch artifact and a rebuild:

1. **If needed, initialize a local git baseline** (only when `/root/druid` is *not* already a git checkout).

   This makes patch emission deterministic: you get a real diff against a baseline commit.

   ```bash
   skills/jackson-security/scripts/druid_emit_patch.sh --init-git
   ```

2. **Edit source** under `/root/druid/` (keep changes minimal and well-scoped).

3. **Emit a patch file** under `/root/patches/` (expected by many verifiers):

   ```bash
   skills/jackson-security/scripts/druid_emit_patch.sh fix-jackson-inject-empty-key.patch
   ```

   If the patch is empty, the script will fail fast—make sure you actually changed code under `/root/druid/`.

4. **Validate and apply the patch**:

   ```bash
   skills/jackson-security/scripts/druid_apply_patch.sh /root/patches/fix-jackson-inject-empty-key.patch
   ```

5. **Build indexing-service and dependencies** (skip web-console and quality gates):

   ```bash
   mvn -f /root/druid/pom.xml \
     -pl indexing-service -am \
     clean package \
     -Pskip-static-checks -Pskip-tests
   ```

Avoid building the root reactor without `-pl ...` unless explicitly required, since that can pull in `web-console`.

## Helper scripts (optional)

If this skill bundle includes helper scripts, you can use them to reduce mistakes:

- `skills/jackson-security/scripts/druid_emit_patch.sh <name>.patch`
- `skills/jackson-security/scripts/druid_apply_patch.sh /root/patches/<name>.patch`
- `skills/jackson-security/scripts/druid_build_indexing_service.sh`

---

# Jackson Deserialization Security

## Key Concept: Deserialization Timing

Jackson transforms JSON text into Java objects during a single `readValue()` call. This transformation is **not** a simple data copy—Jackson interprets JSON structure, resolves types, handles special keys, and instantiates objects all within this operation.

    JSON String → [Jackson Processing] → Java Object
                        ↑
                Attack surface here

Once deserialization completes, the resulting Java object contains no trace of how it was constructed. Any special JSON structures, unusual keys, or type directives that influenced object creation are no longer visible.

---

## Why Post-Deserialization Validation Is Insufficient

Consider the lifecycle of a typical JSON endpoint:

    1. HTTP request arrives with JSON body
    2. Framework deserializes JSON → Java object (Jackson runs here)
    3. Your code receives the Java object
    4. Your code validates the object
    5. Your code processes the object

Validation at step 4 examines the **result** of deserialization, not the **process**. Any malicious behavior triggered during step 2 has already executed. The Java object you're validating may appear completely normal while the attack has already succeeded.

This creates a fundamental blind spot: attacks that exploit Jackson's parsing behavior—rather than the final object state—cannot be detected by examining the deserialized object.

---

## The Empty Key (`""`) Attack Vector

### What Is It?

JSON permits empty strings as object keys:

    {
      "name": "legitimate",
      "": "injected value"
    }

This is valid JSON per RFC 8259. Jackson parses it without error.

### Why Does It Matter?

Some applications and frameworks assign special meaning to empty keys:

- **Injection points**: Certain Jackson configurations use `""` to set values on the root object or trigger special handling
- **Property override**: Empty keys may interact unexpectedly with `@JsonAnySetter` or custom deserializers
- **Framework behaviors**: Some frameworks interpret `""` as "apply to parent" or "default target"

### The Visibility Problem

After deserialization, there is no standard way to know an empty key was present:

    // Original JSON: {"name": "test", "": "malicious"}
    MyObject obj = mapper.readValue(json, MyObject.class);
    // obj.getName() returns "test"
    // Where did "" go? Depends on configuration. You cannot tell from obj.

The attack's effectiveness depends on the specific Jackson configuration and target class—but the defender examining only the resulting object cannot determine whether `""` was used.

---

## Hardening `@JacksonInject` Against Input Override (`useInput`) and Empty-Key Attacks

`@JacksonInject` is commonly used to supply server-side configuration (feature flags, security config, shared services) into objects deserialized from user-controlled JSON. Starting with Jackson 2.9, injected values can be **optionally overridden by input**.

Key points:

- `@JacksonInject(useInput = OptBoolean.DEFAULT)` behaves like `TRUE` for backwards compatibility: **if a matching JSON property is present, it overrides the injected value**.
- This is especially risky for **creator (constructor/factory) parameters** whose logical property name is missing or unstable (for example, when code is compiled without Java `-parameters`). Some Jackson paths treat such names as an empty string, so a JSON property named `""` may match and override the injected value.

Defenses:

1. **Disable input override for security-sensitive injections**
   - Prefer `@JacksonInject(useInput = OptBoolean.FALSE)` for injected configuration and other values that must never be user-controlled.
   - Treat this as the default for "server config" style injections; only allow override when you have a concrete, reviewed reason.

2. **Watch out for custom `AnnotationIntrospector` implementations**
   - Jackson 2.9 introduced `AnnotationIntrospector#findInjectableValue(AnnotatedMember)` returning `JacksonInject.Value` (which carries `useInput`).
   - If your code overrides only the deprecated `findInjectableValueId(...)` (common in older integrations), the base implementation will return an injectable value **without** the `useInput` flag, silently falling back to the default behavior (effectively allowing input override).
   - In other words: adding `useInput = OptBoolean.FALSE` on annotations may do **nothing** unless your introspector propagates it.

   Minimal safe pattern (pseudocode):

   ```java
   @Override
   public JacksonInject.Value findInjectableValue(AnnotatedMember m) {
     JacksonInject ann = m.getAnnotation(JacksonInject.class);
     if (ann == null) return null;

     Object id = computeInjectionId(m);   // e.g., Guice Key, a string id, etc.
     return JacksonInject.Value.from(ann).withId(id);
   }
   ```

   You may also choose to default `useInput` to `false` for all injections, but confirm that no legitimate API relies on overriding injected values from JSON.

3. **Do not rely on post-deserialization validation to detect `""`**
   - If you must outright reject empty-string keys for specific endpoints, perform validation on the raw JSON structure (`JsonParser`/`JsonNode`) **before** binding to a POJO, because the key may not be observable after deserialization.

---

## Other Structural Attack Patterns

### Polymorphic Type Handling

When Jackson is configured with `@JsonTypeInfo`, JSON can specify which class to instantiate:

    {
      "@class": "com.attacker.MaliciousClass",
      "command": "rm -rf /"
    }

Jackson will attempt to instantiate whatever class is named. If the classpath contains exploitable "gadget" classes, arbitrary code execution may occur during deserialization—before your code ever runs.

The resulting object might be the expected type (if the attack class is a subtype), or deserialization might succeed partially before the damage is done.

### Duplicate Keys

JSON does not prohibit duplicate keys. Jackson's default behavior: **last value wins**.

    {
      "role": "user",
      "role": "admin"
    }

Jackson produces an object where `role` equals `"admin"`.

If upstream validation (like a WAF or input filter) checks only the first occurrence while Jackson uses the last, the validation and processing see different values.

### Nested Injection

Deeply nested structures can bypass depth-limited validation:

    {
      "config": {
        "settings": {
          "internal": {
            "": "payload"
          }
        }
      }
    }

Simple string checks might miss patterns buried in nested structures.
