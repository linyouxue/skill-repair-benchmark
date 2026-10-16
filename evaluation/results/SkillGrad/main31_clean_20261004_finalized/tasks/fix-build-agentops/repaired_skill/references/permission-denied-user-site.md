# Permission denied during install to user-site / scripts directory

Use this when an evaluator fails during `pip install ...` with `Permission denied` / `EACCES`, often while writing console scripts into a user bin directory (e.g., `~/.local/bin`) or other unwritable paths.

## Procedure: confirm it is environmental vs repo-fixable

1. **Capture the exact failing command and where it is trying to write.**
   - Copy the full `pip install ...` invocation.
   - Note the destination path from the error message.
2. **Inspect install destinations and user-site behavior.**
   - Whether a venv is active.
   - Whether user-site is enabled.
   - Where scripts will be written.
3. **Branch on who controls the boundary entrypoint** (repo vs harness).

```python
import os
import site
import sys
import sysconfig

print("VIRTUAL_ENV:", os.environ.get("VIRTUAL_ENV"))
print("user site enabled:", site.ENABLE_USER_SITE)
print("usersitepackages:", getattr(site, "getusersitepackages", lambda: None)())
print("scripts:", sysconfig.get_path("scripts"))
print("base_prefix:", sys.base_prefix)
print("prefix:", sys.prefix)
```

### Branch A — evaluator/harness controls install mode (you cannot change it)

If you cannot change how the evaluator runs `pip install` (common in benchmarks/CI harnesses):

- Treat **permission denied to the install destination** as the primary failure.
- Conclude it is **not reliably fixable from repo code**.
- Avoid chasing downstream packaging errors (PEP 660, build backend warnings) unless you can show the permission error is gone.

### Branch B — repo controls the entrypoint (you can change it)

If the repo provides the install/test entrypoint used by CI (e.g., a workflow script, `tox`, `nox`, `make test`):

- Change the entrypoint to run in an isolated, writable environment:
  - create/activate a venv, or
  - use a tool that creates one (tox/nox/uv).
- Ensure the boundary install uses that environment consistently.

## Verification (must close the loop)

1. Re-run the **same failing install command in the same mode**.
2. Confirm the permission error is gone.

If verification fails (permission denied persists):
- **Corrective action:** stop modifying packaging metadata; instead, either (a) change the repo-controlled entrypoint to use an isolated environment (Branch B), or (b) document that the failure is environmental and cannot be fixed from the repository alone (Branch A).
