---
name: planning-with-files
description: Use persistent on-disk planning (`task_plan.md`, `findings.md`, `progress.md`)
  to manage multi-step file-organization tasks with many tool calls and verification
  steps.
allowed-tools:
- Read
- Write
- Edit
- Bash
- Glob
- Grep
- WebFetch
- WebSearch
metadata:
  version: 2.1.2
  user-invocable: true
  hooks:
    SessionStart:
    - hooks:
      - type: command
        command: echo '[planning-with-files] Ready. Auto-activates for complex tasks,
          or invoke manually with /planning-with-files'
    PreToolUse:
    - matcher: Write|Edit|Bash
      hooks:
      - type: command
        command: cat task_plan.md 2>/dev/null | head -30 || true
    PostToolUse:
    - matcher: Write|Edit
      hooks:
      - type: command
        command: echo '[planning-with-files] File updated. If this completes a phase,
          update task_plan.md status.'
    Stop:
    - hooks:
      - type: command
        command: ${CLAUDE_PLUGIN_ROOT}/scripts/check-complete.sh
---

## Steps
1. Create `task_plan.md`, `findings.md`, `progress.md` in the working project directory.
2. Write the non-negotiables into `task_plan.md` (required folder names, “each file exactly once”, “no renames/content edits”, verification checks).
3. Log key discoveries and tool constraints in `findings.md` (e.g., available extractors like `pdftotext`, missing `pandoc/markitdown`, fallback plan).
4. Update `progress.md` as moves occur (counts moved per folder, any low-confidence items flagged for review).
5. Before finalizing, re-read `task_plan.md` and run the verification checklist; record results in `progress.md`.
## Expected Result
The task remains coherent across many actions, errors are not repeated, and final completeness/correctness checks are explicit and recorded.
