# Final-turn lint (user-facing completion)

Use this when you notice you are about to send a meta-template (e.g., “Summary: …”, “Finish with message: …”, TODO blocks) instead of the actual final answer.

## Trigger

Read this chapter when your draft final message contains any of:
- “Summary:” / “Finish with message:” / “TODO”
- placeholders like “replace this” / “fill in”
- self-referential instructions about what you *will* say

Skip when the final message already reads like a normal user-facing completion.

## Procedure

1. **Delete scaffolding first.** Remove headings like “Summary:” if they are part of a template rather than the actual response.
2. **Write the completion contract (3 lines):**
   - **Changes:** what files/artifacts were created/updated.
   - **Verification:** what you actually ran/checked (commands, tests, or inspections).
   - **Limits:** what you could not verify and why (only if applicable).
3. **Check for forbidden text.** Ensure none of the scaffold markers remain.

```python
def final_turn_lint(text: str) -> None:
    banned = [
        "Finish with message",
        "Summary:",
        "TODO",
        "template",
        "placeholder",
        "replace this",
        "fill in",
    ]
    hits = [b for b in banned if b in text]
    if hits:
        raise ValueError(f"Remove meta/template markers from final response: {hits}")

    # Runtime branch: completion vs. still-draft
    lower = text.lower()
    completion_signals = ["created", "updated", "added", "changed", "verified", "could not verify"]
    if not any(s in lower for s in completion_signals):
        raise ValueError("Final response doesn't look like a completion; add changes + verification")


def verify_and_fix(text: str) -> str:
    try:
        final_turn_lint(text)
        return text
    except ValueError as e:
        # Corrective action: rewrite into the completion contract.
        raise ValueError(
            f"Final-turn lint failed: {e}. Rewrite as: Changes + Verification + Limits (if any)."
        )
```

## Verification (and corrective action)

- Re-run `final_turn_lint()` on the rewritten final message.
- If it still fails: **stop adding content** and rewrite into exactly three bullets (Changes / Verification / Limits) until the lint passes.
