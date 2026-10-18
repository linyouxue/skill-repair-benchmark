# Build-fix loop: tracing missing-symbol failures to a patch

Load this chapter when a test failure's traceback names a symbol
(`AttributeError`, `NameError`, `ImportError` on an in-repo module) that
should exist on an in-repo class or module. The goal: localize every
**reference** vs. every **assignment** of the symbol, then add the missing
initialization (or rename to match an existing attribute) as the next patch.

## Trigger

Trigger shapes to recognize:

- `AttributeError: '<ProjectClass>' object has no attribute '<name>'`
- `NameError: name '<name>' is not defined` inside a project module
- `ImportError: cannot import name '<name>' from '<project.module>'`
- A test uses an attribute/method that `grep` shows is read but never
  assigned anywhere in the package.

Do **not** load this chapter for third-party `ModuleNotFoundError`
(wrap in `try/except ImportError` or add the dep) or for pytest fixture
errors (fix the fixture).

## Procedure

### Branch A — missing attribute on an in-repo class

Run both greps. The two result sets together tell you whether the symbol is
never assigned (missing init), assigned under a different name (rename
needed), or assigned behind a conditional that didn't fire.

```python
import subprocess

symbol = "_tags_for_future_session"      # from the traceback
package = "agentops"                      # the project's top-level package

# All reads: attribute access, kwargs, strings in getattr
reads = subprocess.run(
    ["grep", "-RnE", rf"[^A-Za-z_]{symbol}\b", package],
    capture_output=True, text=True,
).stdout

# All assignments: `self.<sym> =`, `<sym> =`, setattr
writes = subprocess.run(
    ["grep", "-RnE", rf"(self\.{symbol}\s*=|^\s*{symbol}\s*=|setattr\([^,]+,\s*['\"]{symbol}['\"])", package],
    capture_output=True, text=True,
).stdout

print("READS:\n", reads)
print("WRITES:\n", writes)
```

Classify the output:

- **Reads non-empty, writes empty → missing initialization.** Add the
  assignment in the class's `__init__` (or wherever the related state is
  built) with a sensible default — usually matching the type of a sibling
  attribute (e.g. `self._tags_for_future_session: list[str] = []`).
- **Reads non-empty, writes exist but under a conditional that didn't
  fire → unconditional default needed.** Lift a default assignment above the
  conditional in `__init__`.
- **Reads non-empty, writes under a different attribute name → rename.**
  Rename one side to match the other; prefer renaming the typo'd side.

### Branch B — missing name in a project module

```python
# Replace the attribute grep with a module-symbol grep
symbol = "some_function"
package = "myproject"
subprocess.run(["grep", "-RnE", rf"\bdef\s+{symbol}\b|\b{symbol}\s*=",
                package], check=False)
```

If `def` / assignment is absent, either (a) add the missing definition
guided by call sites, or (b) correct the import to point at the real
location.

## Worked example (iter_0 fix-build-agentops)

Traceback: `AttributeError: 'Client' object has no attribute '_tags_for_future_session'`
on `tests/test_events.py::TestEvents::test_record_timestamp`.

1. Grep for reads of `_tags_for_future_session` in `agentops/` →
   several hits in `client.py` (`add_tags`, session-creation path).
2. Grep for assignments → none in `Client.__init__`.
3. Diagnosis: missing initialization. Fix: add
   `self._tags_for_future_session = []` (or the type matching sibling
   state) in `Client.__init__` near the other instance attributes.
4. Re-run the full test command captured earlier.

## Verification

After writing the patch, run the project's full test command (the one
captured in SKILL.md's first section). Two outcomes:

- **Exit 0, full suite green → done.** Record the final patch set.
- **Exit non-zero → inspect every remaining failure.** For each one,
  return to the top of this chapter if it is another missing-symbol
  failure, otherwise return to SKILL.md's patch–rerun loop and classify
  afresh. Do **not** declare success on partial progress, and do **not**
  reclassify a still-failing test as out-of-scope without the evidence
  rule in SKILL.md.

If the same `AttributeError` persists after your patch, the assignment
you added is unreachable (wrong class, wrong `__init__`, shadowed by a
subclass). Re-run the two greps — the write-set should now include your
new line; if it doesn't, you edited the wrong file.
