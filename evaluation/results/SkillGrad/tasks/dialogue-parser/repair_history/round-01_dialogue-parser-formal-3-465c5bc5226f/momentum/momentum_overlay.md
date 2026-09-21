### [Task dialogue-parser] missing required output artifacts (dialogue.json, dialogue.dot)
- signal: failure
- pattern: always-write-required-artifacts
- anchor: (none)
- gap: The run never reached/never executed the final pipeline step that materializes deliverables. There is no evidence of any “write outputs” action; output inventory is empty (neither `/app/dialogue.json` nor `/app/dialogue.dot` exists).
- proposed_change: Add an explicit end-of-task “deliverables” rule to SKILL.md: (1) list required artifacts and paths; (2) after building the graph/dict, always write `/app/dialogue.json` and a Graphviz `.dot` file (or use the library’s visualization/export helpers) even if parsing is partial; (3) finish with a post-write check that both files exist, are non-empty, and JSON is loadable.

## WORKFLOW-THEMES

- (none this iteration)
