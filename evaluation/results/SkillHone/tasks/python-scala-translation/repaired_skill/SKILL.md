---
name: skillsbench-python-scala-translation-bundle
description: Maintain the complete task-specific Agent Skill bundle under skills/.
---

# SkillsBench bundle maintenance

The deployable bundle is the complete `skills/` directory. Inspect and improve
the relevant nested `SKILL.md`, scripts, and references there. This top-level
file exists only so SkillHone can track a multi-Skill bundle as one repository;
it is not deployed by the evaluator.

Make focused, generalizable changes. Do not encode the visible task instance,
expected output, verifier behavior, or benchmark answer. Do not edit anything
outside `skills/` except ordinary local test files when genuinely reusable.
