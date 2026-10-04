### [data-to-d3] Tooltip missing required “name” field due to missing prompt→tooltip binding verification
- signal: failure
- pattern: tooltip-requirements-binding-checklist
- anchor: interactive-features-tooltips-click-handlers-hover-effects
- gap: The final `tooltip.html(...)` template included ticker, fullName, and sector, but did not render a distinct “name” field as required by the prompt (“ticker, name, and sector”). The implementation assumed CSV “full name” ≈ company name but did not bind it to the prompt’s required label (“name”), so a strict grader check fails. There was no field-by-field verification step (e.g., grep/read the final tooltip HTML string) to ensure all required fields were present.
- proposed_change: Patch L2 under **Interactive features (tooltips, click handlers, hover effects)** to add a “requirements-to-tooltip binding checklist”: (1) list required tooltip fields verbatim from the prompt, (2) map each to a specific data property/CSV column (e.g., prompt “name” → CSV “full name” → `d.fullName`), (3) require rendering with the prompt’s labels, and (4) require a final static verification pass (open/grep `tooltip.html(`) confirming each required label/value is present. Also add a note to implement and verify explicit guards for elements that must not show tooltips (e.g., ETFs) using the prompt’s definition.

## WORKFLOW-THEMES

- (none this iteration)
