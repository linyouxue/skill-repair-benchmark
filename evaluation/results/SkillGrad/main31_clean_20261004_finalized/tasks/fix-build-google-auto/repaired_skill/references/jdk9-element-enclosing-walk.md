# JDK 9+ element enclosing walk: stop at PACKAGE, handle MODULE

JDK 9 introduced module elements into the `javax.lang.model.element.Element` hierarchy. Code that computes names/visibility by walking `Element.getEnclosingElement()` can accidentally include a module (or otherwise walk past the logical package boundary), producing incorrect fully-qualified names or access rules.

Read this when a build passes dependency resolution/compilation but tests or annotation-processor logic fail with wrong names/visibility after a JDK upgrade.

## Procedure

1. Find the method that derives a name/visibility by repeatedly calling `getEnclosingElement()`.
2. Decide what your algorithm conceptually expects as a boundary.
   - For type name composition, the boundary is typically the *package*.
   - For visibility, the boundary is typically the *package* (or the top-level type), depending on the rule.
3. Implement a traversal that:
   - stops when it hits `ElementKind.PACKAGE`
   - explicitly handles `ElementKind.MODULE` (usually: skip it and stop, or treat it as a hard stop)
4. Re-run the exact `mvn ... verify` command; do not assume the fix is correct until tests are green.

## Runnable example (Python model of the traversal)

```python
from dataclasses import dataclass

@dataclass
class E:
    kind: str
    name: str
    enclosing: "E | None" = None

def enclosing_chain(elem: E):
    chain = []
    while elem is not None:
        chain.append((elem.kind, elem.name))
        # Branch A: stop at the package boundary
        if elem.kind == "PACKAGE":
            break
        # Branch B: JDK9+ module element present; treat as a hard boundary
        if elem.kind == "MODULE":
            break
        elem = elem.enclosing
    return chain

# Example structure: TYPE -> PACKAGE -> MODULE
module = E("MODULE", "java.base")
pkg = E("PACKAGE", "com.example", enclosing=module)
type_elem = E("TYPE", "Widget", enclosing=pkg)

print(enclosing_chain(type_elem))
```

## Java-oriented sketch

Use the `ElementKind` boundary checks in the loop; keep it minimal and deterministic.

```java
Element e = start;
while (e != null) {
  ElementKind k = e.getKind();
  if (k == ElementKind.PACKAGE) {
    break;
  }
  if (k == ElementKind.MODULE) {
    break; // or: e = e.getEnclosingElement(); continue; depending on semantics
  }
  e = e.getEnclosingElement();
}
```

## Verification

- Verify: run the exact target build command (e.g., `mvn ... verify`) and confirm:
  - the failing tests that asserted names/visibility are now green, and
  - no new failures appear later in the reactor.

If verification fails:
- If failures still show *wrong names* (extra prefix segments, duplicated package, etc.), log the observed enclosing chain by printing each element kind/name during traversal, then adjust the stop/skip behavior for `MODULE`.
- If failures moved from tests to compilation errors, ensure your traversal change did not alter null-handling; add a defensive `e != null` check and re-run.
