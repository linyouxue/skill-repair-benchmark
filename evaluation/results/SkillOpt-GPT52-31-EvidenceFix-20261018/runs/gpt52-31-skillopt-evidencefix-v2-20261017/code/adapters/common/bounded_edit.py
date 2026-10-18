"""Bounded skill edits (SkillOpt-style patch ops) for the eva adapter."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable


class BoundedEditValidationError(ValueError):
    """Raised when every bounded-edit response violates the edit contract."""

    def __init__(self, message: str, *, attempts: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.attempts = attempts or []


def _edit_contract_errors(
    parsed: dict[str, Any] | None,
    *,
    skill_content: str,
    budget_l: int,
) -> tuple[list[dict[str, Any]], str, list[str]]:
    """Validate and normalize an edit response without silently coercing fields."""
    if not isinstance(parsed, dict):
        return [], "", ["response is not a JSON object"]
    reasoning = str(parsed.get("reasoning", "")).strip()
    raw_edits = parsed.get("edits")
    if not isinstance(raw_edits, list) or not raw_edits:
        return [], reasoning, ["edits must be a non-empty array"]

    errors: list[str] = []
    if len(raw_edits) > budget_l:
        errors.append(f"edits contains {len(raw_edits)} items, exceeding budget {budget_l}")

    clean: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_edits[:budget_l], start=1):
        prefix = f"edits[{idx - 1}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        op = str(item.get("op", "")).strip()
        if op not in {"append", "insert_after", "replace", "delete"}:
            errors.append(f"{prefix}.op is invalid: {op!r}")
            continue
        aliases = [name for name in ("replacement", "value", "text", "new_text") if name in item]
        if aliases:
            errors.append(
                f"{prefix} uses unsupported replacement field(s) {aliases}; use content only"
            )
        target = str(item.get("target", "") or "")
        if op in {"insert_after", "replace", "delete"}:
            if not target:
                errors.append(f"{prefix}.target is required for {op}")
            elif target not in skill_content:
                errors.append(f"{prefix}.target is not an exact substring of the current skill")

        if op == "delete":
            content = ""
        else:
            if "content" not in item:
                errors.append(f"{prefix}.content is required for {op}")
                content = ""
            else:
                content = str(item.get("content") or "")
                if not content.strip():
                    errors.append(f"{prefix}.content must be non-empty for {op}")
        clean.append({"op": op, "target": target, "content": content})
    return clean, reasoning, errors


def apply_edits_local(skill: str, edits: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """Apply already validated edits atomically without importing upstream."""
    reports: list[dict[str, Any]] = []
    text = skill
    for idx, edit in enumerate(edits, start=1):
        if not isinstance(edit, dict):
            raise BoundedEditValidationError(f"edit {idx} is not an object")
        op = str(edit.get("op", "")).strip()
        if op != "delete" and ("content" not in edit or not str(edit.get("content") or "").strip()):
            raise BoundedEditValidationError(f"edit {idx} has no non-empty content for {op}")
        content = "" if op == "delete" else str(edit["content"])
        target = str(edit.get("target", "") or "")
        report: dict[str, Any] = {
            "index": idx,
            "op": op,
            "target": target[:200],
            "content_preview": content[:200],
            "status": "unknown",
        }
        if op == "append":
            text = text.rstrip() + "\n\n" + content.rstrip() + "\n"
            report["status"] = "applied_append"
        elif op == "insert_after":
            if not target or target not in text:
                raise BoundedEditValidationError(f"edit {idx} insert_after target not found")
            at = text.index(target) + len(target)
            nl = text.find("\n", at)
            insert_at = nl + 1 if nl != -1 else len(text)
            text = text[:insert_at] + "\n" + content.rstrip() + "\n" + text[insert_at:]
            report["status"] = "applied_insert_after"
        elif op == "replace":
            if not target:
                raise BoundedEditValidationError(f"edit {idx} replace target is missing")
            elif target not in text:
                raise BoundedEditValidationError(f"edit {idx} replace target not found")
            text = text.replace(target, content, 1)
            report["status"] = "applied_replace"
        elif op == "delete":
            if not target:
                raise BoundedEditValidationError(f"edit {idx} delete target is missing")
            elif target not in text:
                raise BoundedEditValidationError(f"edit {idx} delete target not found")
            text = text.replace(target, "", 1)
            report["status"] = "applied_delete"
        else:
            raise BoundedEditValidationError(f"edit {idx} has unknown op {op!r}")
        reports.append(report)
    if not text.endswith("\n"):
        text += "\n"
    return text, reports


def propose_bounded_edits(
    *,
    chat_fn: Callable[..., tuple[str, dict[str, Any]]],
    extract_json_fn: Callable[[str], dict[str, Any] | None],
    fallback_extract_fn: Callable[[str], dict[str, Any] | None],
    skill_content: str,
    skill_path: str,
    task_id: str,
    diagnosis_item: dict[str, Any],
    task_context: str,
    baseline_source_type: str,
    baseline_context: str,
    budget_l: int,
    rejected_buffer: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], str, dict[str, Any], str, list[dict[str, Any]]]:
    """Ask optimizer for ≤L edits, retrying responses that violate the contract."""
    system = (
        "You are a SkillOpt bounded skill editor. Propose AT MOST "
        f"{budget_l} structured edits (learning-rate budget). "
        "Use only ops: append, insert_after, replace, delete. "
        "For insert_after/replace/delete, target MUST be an exact substring of the current skill. "
        "Do not rewrite the whole document. Do not invent gold answers. "
        "Return exactly one JSON object with keys reasoning:string and edits:array. "
        "Every edit must use keys op, target, and content. For append, insert_after, "
        "and replace, content is REQUIRED and MUST be non-empty. For delete, content "
        "must be an empty string. Never use replacement, value, text, or new_text."
    )
    user_parts = [
        f"## Task ID\n{task_id}",
        f"## Skill Path\n{skill_path}",
        f"## Diagnosis\n{json.dumps(diagnosis_item, ensure_ascii=False, indent=2)}",
        f"## Current Skill\n{skill_content}",
        f"## Task Context\n{task_context}",
        f"## Baseline Evidence ({baseline_source_type})\n{baseline_context}",
        f"Propose at most {budget_l} edits that implement the repair instruction.",
    ]
    if rejected_buffer:
        user_parts.insert(
            -1,
            "## Rejected Edits From Earlier Rounds (do not repeat)\n"
            + json.dumps(rejected_buffer[-8:], ensure_ascii=False, indent=2),
        )
    base_user = "\n\n".join(user_parts)
    max_attempts = max(1, int(os.environ.get("SKILLOPT_EVA_EDIT_FORMAT_ATTEMPTS", "3") or 3))
    attempts: list[dict[str, Any]] = []
    last_errors: list[str] = []
    for attempt_no in range(1, max_attempts + 1):
        user = base_user
        if last_errors:
            user += (
                "\n\n## Previous response rejected\n"
                + json.dumps(last_errors, ensure_ascii=False, indent=2)
                + "\nRegenerate the entire JSON object using only the required content field."
            )
        request_record = {
            "stage": "bounded_edit",
            "attempt": attempt_no,
            "model": os.environ.get("SKILLOPT_MODEL", ""),
            "system": system,
            "user": user,
            "parameters": {"max_completion_tokens": 12000, "budget_l": budget_l},
        }
        raw_text = ""
        usage: dict[str, Any] = {}
        try:
            raw_text, usage = chat_fn(system=system, user=user)
            parsed = extract_json_fn(raw_text) or fallback_extract_fn(raw_text)
            clean, reasoning, errors = _edit_contract_errors(
                parsed if isinstance(parsed, dict) else None,
                skill_content=skill_content,
                budget_l=budget_l,
            )
        except Exception as exc:  # noqa: BLE001
            parsed = None
            clean, reasoning = [], ""
            errors = [f"optimizer call or response parsing failed: {exc!r}"]
        attempts.append(
            {
                "attempt": attempt_no,
                "request": request_record,
                "response": {"raw_text": raw_text, "usage": usage},
                "parsed": parsed,
                "validation_errors": errors,
                "accepted": not errors,
            }
        )
        if not errors:
            return clean, reasoning, usage, raw_text, attempts
        last_errors = errors
    raise BoundedEditValidationError(
        f"bounded edit response remained invalid after {max_attempts} attempts: {last_errors}",
        attempts=attempts,
    )


def patch_skill_with_fallback_rewrite(
    *,
    skill_content: str,
    skill_path: str,
    task_id: str,
    diagnosis_item: dict[str, Any],
    task_context: str,
    baseline_source_type: str,
    baseline_context: str,
    budget_l: int,
    update_mode: str,
    rejected_buffer: list[dict[str, Any]] | None,
    propose_chat_fn: Callable[..., tuple[str, dict[str, Any]]],
    extract_json_fn: Callable[[str], dict[str, Any] | None],
    fallback_extract_fn: Callable[[str], dict[str, Any] | None],
    rewrite_fn: Callable[[], dict[str, Any]],
    raw_log_path: Path,
    write_json_fn: Callable[[Path, dict[str, Any]], None],
) -> dict[str, Any]:
    """Patch by default; if no applied edits (or mode=rewrite), call rewrite_fn."""
    mode = (update_mode or "patch").strip().lower()
    if mode == "rewrite":
        result = rewrite_fn()
        result["update_mode_used"] = "rewrite"
        result["edit_reports"] = []
        result["fallback_reason"] = None
        return result

    try:
        edits, reasoning, usage, raw_text, attempts = propose_bounded_edits(
            chat_fn=propose_chat_fn,
            extract_json_fn=extract_json_fn,
            fallback_extract_fn=fallback_extract_fn,
            skill_content=skill_content,
            skill_path=skill_path,
            task_id=task_id,
            diagnosis_item=diagnosis_item,
            task_context=task_context,
            baseline_source_type=baseline_source_type,
            baseline_context=baseline_context,
            budget_l=budget_l,
            rejected_buffer=rejected_buffer,
        )
    except BoundedEditValidationError as exc:
        write_json_fn(
            raw_log_path,
            {
                "ok": False,
                "update_mode": "patch",
                "error": str(exc),
                "format_validation_failed": True,
                "attempts": exc.attempts,
            },
        )
        raise
    new_skill, reports = apply_edits_local(skill_content, edits)
    applied = sum(1 for r in reports if str(r.get("status", "")).startswith("applied_"))
    write_json_fn(
        raw_log_path,
        {
            "ok": applied > 0,
            "update_mode": "patch",
            "edits": edits,
            "edit_reports": reports,
            "applied_count": applied,
            "usage": usage,
            "raw_text": raw_text,
            "reasoning": reasoning,
            "attempts": attempts,
        },
    )
    if applied > 0 and new_skill.strip() and new_skill != skill_content:
        return {
            "new_skill": new_skill,
            "change_summary": [
                f"{r.get('op')}:{r.get('status')}" for r in reports if str(r.get("status", "")).startswith("applied_")
            ],
            "reasoning": reasoning,
            "update_mode_used": "patch",
            "edit_reports": reports,
            "proposed_edits": edits,
            "fallback_reason": None,
        }

    # Fallback to full rewrite
    result = rewrite_fn()
    result["update_mode_used"] = "rewrite_fallback"
    result["edit_reports"] = reports
    result["proposed_edits"] = edits
    result["fallback_reason"] = "no_applied_bounded_edits"
    return result
