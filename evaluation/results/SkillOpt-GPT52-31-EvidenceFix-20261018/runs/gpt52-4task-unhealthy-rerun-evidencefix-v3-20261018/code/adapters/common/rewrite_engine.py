from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from adapters.common.executor_api import write_json
from adapters.common.paths import ROOT, SKILLOPT_ROOT, task_dir
from adapters.common.bounded_edit import patch_skill_with_fallback_rewrite
from adapters.common.method_profile import method_profile
from adapters.common.repair_loop import (
    diagnosis_parallel,
    diagnosis_sample_count,
    edit_budget_l,
    merge_diagnosis_samples,
    pick_loose_diagnosis,
    repair_rounds_r,
    run_diagnosis_samples,
    smoke_mode,
    truncate_diagnosed_skills,
)


def _env_flag(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def shared_diagnosis_dir(run_id: str, task_id: str, repair_round: int = 1, method_name: str = "skillopt") -> Path:
    # Per-method cache so SO (merge) and Lite (loose pick) do not collide.
    safe_method = (method_name or "skillopt").replace("/", "_")
    return ROOT / "experiments" / run_id / "shared" / task_id / f"round_{repair_round}" / safe_method


def infer_run_id_from_workspace(workspace: Path) -> str | None:
    """Infer run_id from .../experiments/<run_id>/methods/<method>/<task>/workspace."""
    try:
        resolved = workspace.resolve()
        parts = resolved.parts
        if "experiments" not in parts or "methods" not in parts:
            return None
        exp_idx = parts.index("experiments")
        methods_idx = parts.index("methods")
        if methods_idx != exp_idx + 2:
            return None
        return parts[exp_idx + 1]
    except Exception:  # noqa: BLE001
        return None


def load_project_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _expand_env_refs() -> None:
    for key, value in list(os.environ.items()):
        if value.startswith("${") and value.endswith("}"):
            ref = value[2:-1]
            os.environ[key] = os.environ.get(ref, value)


def _missing_or_placeholder(value: str) -> bool:
    stripped = str(value or "").strip()
    return not stripped or "<" in stripped or stripped.startswith("${")


def configure_model_env() -> None:
    load_project_env()
    _expand_env_refs()
    provider = os.environ.get("MODEL_PROVIDER", "").strip().lower()
    tatu_secret = os.environ.get("TATU_API_KEY", "").strip()
    tatu_base = os.environ.get("TATU_BASE_URL", "").strip()
    tatu_model = os.environ.get("TATU_MODEL", "").strip()
    ai360_secret = (
        os.environ.get("AI360_API_KEY", "").strip()
        or os.environ.get("LLM_API_KEY", "").strip()
        or os.environ.get("OPENAI_API_KEY", "").strip()
    )
    ai360_base = (
        os.environ.get("AI360_BASE_URL", "").strip()
        or os.environ.get("LLM_API_BASE", "").strip()
        or os.environ.get("OPENAI_API_BASE", "").strip()
        or os.environ.get("OPENAI_BASE_URL", "").strip()
        or os.environ.get("SKILLOPT_API_BASE", "").strip()
    )
    ai360_model = (
        os.environ.get("SKILLOPT_MODEL", "").strip()
        or os.environ.get("AI360_MODEL", "").strip()
    )

    use_tatu = provider == "tatu" or (
        not _missing_or_placeholder(tatu_secret)
        and not _missing_or_placeholder(tatu_base)
        and _missing_or_placeholder(ai360_secret)
    )
    if use_tatu:
        secret, base_url, model = tatu_secret, tatu_base, tatu_model or ai360_model
        if _missing_or_placeholder(secret):
            raise RuntimeError("TATU_API_KEY is missing. Fill .env before running paid optimization.")
        if _missing_or_placeholder(base_url):
            raise RuntimeError("TATU_BASE_URL is missing. Fill .env with the Tatu OpenAI-compatible base URL.")
        if _missing_or_placeholder(model):
            raise RuntimeError("TATU_MODEL / SKILLOPT_MODEL is missing. Fill .env with the Tatu model id.")
        os.environ["TATU_API_KEY"] = secret
        os.environ["TATU_BASE_URL"] = base_url
        os.environ["TATU_MODEL"] = model
        os.environ["AI360_API_KEY"] = secret
        os.environ["AI360_BASE_URL"] = base_url
        os.environ["AI360_MODEL"] = model
    else:
        secret, base_url, model = ai360_secret, ai360_base, ai360_model
        if _missing_or_placeholder(secret):
            raise RuntimeError("AI360_API_KEY is missing. Fill .env before running paid optimization.")
        if _missing_or_placeholder(base_url):
            raise RuntimeError("AI360_BASE_URL is missing. Fill .env with the 360 OpenAI-compatible base URL.")
        if _missing_or_placeholder(model):
            raise RuntimeError("AI360_MODEL / SKILLOPT_MODEL is missing. Fill .env with the 360 model id.")
        os.environ.setdefault("AI360_API_KEY", secret)
        os.environ.setdefault("AI360_BASE_URL", base_url)
        os.environ.setdefault("AI360_MODEL", model)

    os.environ["SKILLOPT_MODEL"] = model
    os.environ["SKILLOPT_API_BASE"] = base_url

    # Compatibility shims for upstream SkillOpt OpenAI-compatible backends.
    os.environ.setdefault("OPENAI_API_KEY", secret)
    os.environ.setdefault("OPENAI_API_BASE", base_url)
    os.environ.setdefault("OPENAI_BASE_URL", base_url)
    os.environ.setdefault("OPENAI_COMPATIBLE_API_KEY", secret)
    os.environ.setdefault("OPENAI_COMPATIBLE_BASE_URL", base_url)
    os.environ.setdefault("OPENAI_COMPATIBLE_MODEL", model)
    os.environ.setdefault("OPENAI_COMPATIBLE_MAX_TOKENS", "32000")
    os.environ.setdefault("OPENAI_COMPATIBLE_TEMPERATURE", "0")
    os.environ.setdefault("OPTIMIZER_OPENAI_COMPATIBLE_API_KEY", secret)
    os.environ.setdefault("OPTIMIZER_OPENAI_COMPATIBLE_BASE_URL", base_url)
    os.environ.setdefault("OPTIMIZER_OPENAI_COMPATIBLE_MODEL", model)
    os.environ.setdefault("OPTIMIZER_OPENAI_COMPATIBLE_MAX_TOKENS", "32000")
    os.environ.setdefault("OPTIMIZER_OPENAI_COMPATIBLE_TEMPERATURE", "0")

    # SkillOpt-Lite routes OpenAI-compatible auth through the Azure-family backend.
    os.environ.setdefault("AZURE_OPENAI_ENDPOINT", base_url)
    os.environ.setdefault("AZURE_OPENAI_API_KEY", secret)
    os.environ.setdefault("AZURE_OPENAI_AUTH_MODE", "openai_compatible")
    os.environ.setdefault("OPTIMIZER_AZURE_OPENAI_ENDPOINT", base_url)
    os.environ.setdefault("OPTIMIZER_AZURE_OPENAI_API_KEY", secret)
    os.environ.setdefault("OPTIMIZER_AZURE_OPENAI_AUTH_MODE", "openai_compatible")
    os.environ.setdefault("OPTIMIZER_DEPLOYMENT", model)
    os.environ.setdefault("TARGET_DEPLOYMENT", model)


def _uses_tatu_messages() -> bool:
    """Return whether the configured provider requires Anthropic Messages."""
    return os.environ.get("MODEL_PROVIDER", "").strip().lower() == "tatu"


def _tatu_messages_chat(
    *,
    system: str,
    user: str,
    max_completion_tokens: int,
    retries: int,
) -> tuple[str, dict[str, int]]:
    """Call Tatu's Anthropic-compatible Messages endpoint.

    Claude deployments on MaaS do not necessarily expose OpenAI Chat
    Completions. Keep this adapter local to the evaluation harness so the
    upstream SkillOpt checkout remains provider-neutral.
    """
    configure_model_env()
    base_url = os.environ["TATU_BASE_URL"].rstrip("/")
    messages_url = (
        f"{base_url}/messages" if base_url.endswith("/v1") else f"{base_url}/v1/messages"
    )
    api_key = os.environ["TATU_API_KEY"]
    model = os.environ["TATU_MODEL"]
    payload = json.dumps(
        {
            "model": model,
            "max_tokens": max_completion_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        },
        ensure_ascii=False,
    ).encode("utf-8")
    last_error: Exception | None = None
    for attempt in range(max(1, retries)):
        request = urllib.request.Request(
            messages_url,
            data=payload,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=600) as response:  # noqa: S310
                body = json.loads(response.read().decode("utf-8"))
            blocks = body.get("content") or []
            text = "".join(
                str(block.get("text", ""))
                for block in blocks
                if isinstance(block, dict) and block.get("type") == "text"
            )
            if not text.strip():
                raise RuntimeError(f"Tatu Messages returned no text content: {body!r}")
            raw_usage = body.get("usage") or {}
            prompt_tokens = int(raw_usage.get("input_tokens", 0) or 0)
            completion_tokens = int(raw_usage.get("output_tokens", 0) or 0)
            return text, {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            }
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:2000]
            last_error = RuntimeError(f"Tatu Messages HTTP {exc.code}: {detail}")
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        if attempt + 1 < max(1, retries):
            time.sleep(min(2**attempt, 8))
    raise RuntimeError(f"Tatu Messages call failed after {max(1, retries)} attempts: {last_error}")


def short_text(value: Any, limit: int = 18000) -> str:
    text = json.dumps(value, ensure_ascii=False, indent=2) if not isinstance(value, str) else value
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n[truncated to {limit} chars]"


def load_task_context(task_id: str) -> str:
    directory = task_dir(task_id)
    parts: list[str] = []
    for rel in ("task.md", "environment/README.md"):
        path = directory / rel
        if path.is_file():
            parts.append(f"## {rel}\n{short_text(path.read_text(encoding='utf-8', errors='replace'), 12000)}")
    return "\n\n".join(parts)


def _compact_result_payload(data: dict[str, Any]) -> dict[str, Any]:
    focus_keys = [
        "task_passed",
        "comparable",
        "grader_result",
        "verifier_result",
        "error",
        "summary",
        "transcript",
        "messages",
        "trace",
        "stdout",
        "stderr",
        "ok",
        "traceback",
    ]
    compact = {key: data[key] for key in focus_keys if key in data}
    return compact if compact else data


def load_baseline_context(
    baseline_result: Path | None,
    *,
    max_chars: int = 22000,
) -> tuple[str, str]:
    if not baseline_result or not baseline_result.is_file():
        return "mixed", "No baseline result JSON was found for this task in the current run."
    data = json.loads(baseline_result.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return "mixed", short_text(data, max_chars)
    passed = bool(data.get("task_passed"))
    source_type = "success" if passed else "failure"
    return source_type, short_text(_compact_result_payload(data), max_chars)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_head_tail(path: Path, max_chars: int) -> tuple[str, bool]:
    """Read reproducible source excerpts without loading huge trajectories."""
    max_bytes = max(1024, max_chars)
    size = path.stat().st_size
    if size <= max_bytes:
        return path.read_text(encoding="utf-8", errors="replace"), False
    head_bytes = max_bytes // 3
    tail_bytes = max_bytes - head_bytes
    with path.open("rb") as handle:
        head = handle.read(head_bytes)
        handle.seek(max(0, size - tail_bytes))
        tail = handle.read(tail_bytes)
    marker = (
        f"\n\n[... source excerpt truncated; total_bytes={size}; "
        f"head_bytes={len(head)}; tail_bytes={len(tail)} ...]\n\n"
    )
    return (
        head.decode("utf-8", errors="replace")
        + marker
        + tail.decode("utf-8", errors="replace"),
        True,
    )


def _run_root_for_result(result_path: Path) -> Path | None:
    experiments_root = (ROOT / "experiments").resolve()
    for parent in result_path.resolve().parents:
        if parent.parent == experiments_root:
            return parent
    return None


def _job_dir_for_result(result_path: Path, data: dict[str, Any]) -> Path | None:
    run_root = _run_root_for_result(result_path)
    method_id = str(data.get("method_id", "")).strip()
    rollout_id = str(data.get("rollout_id", "")).strip()
    if run_root and method_id and rollout_id:
        local = run_root / "jobs" / method_id / rollout_id
        if local.is_dir():
            return local
    raw = str(data.get("rollout_dir", "")).strip()
    if raw:
        external = Path(raw)
        if external.is_dir():
            return external
    return None


def _source_record(
    *,
    role: str,
    path: Path,
    included_chars: int,
    truncated: bool,
) -> dict[str, Any]:
    return {
        "role": role,
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
        "included_chars": included_chars,
        "truncated_in_model_context": truncated,
    }


def _detailed_result_context(
    *,
    label: str,
    result_path: Path,
    max_chars: int,
) -> tuple[str, str, dict[str, Any]]:
    data = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        text = short_text(data, max_chars)
        return "mixed", text, {
            "label": label,
            "result_path": str(result_path),
            "job_dir": None,
            "sources": [
                _source_record(
                    role="evaluation_result",
                    path=result_path,
                    included_chars=len(text),
                    truncated=len(text) >= max_chars,
                )
            ],
        }

    source_type = "success" if data.get("task_passed") is True else "failure"
    job_dir = _job_dir_for_result(result_path, data)
    sections: list[str] = []
    sources: list[dict[str, Any]] = []

    result_budget = max(2500, int(max_chars * 0.14))
    result_text = short_text(_compact_result_payload(data), result_budget)
    sections.append(f"#### Evaluation result\n{result_text}")
    sources.append(
        _source_record(
            role="evaluation_result",
            path=result_path,
            included_chars=len(result_text),
            truncated=result_path.stat().st_size > result_budget,
        )
    )

    candidates: list[tuple[str, Path, int]] = []
    if job_dir:
        candidates = [
            ("verifier_structured_checks", job_dir / "verifier" / "ctrf.json", int(max_chars * 0.24)),
            ("verifier_stdout", job_dir / "verifier" / "test-stdout.txt", int(max_chars * 0.24)),
            ("agent_llm_trajectory", job_dir / "trajectory" / "llm_trajectory.jsonl", int(max_chars * 0.32)),
            ("verifier_events", job_dir / "trainer" / "verifiers.jsonl", int(max_chars * 0.06)),
        ]
    for role, path, budget in candidates:
        if not path.is_file():
            continue
        excerpt, truncated = _read_head_tail(path, max(1200, budget))
        sections.append(f"#### {role}\n{excerpt}")
        sources.append(
            _source_record(
                role=role,
                path=path,
                included_chars=len(excerpt),
                truncated=truncated,
            )
        )

    context = "\n\n".join(sections)
    if len(context) > max_chars:
        context = context[:max_chars] + f"\n\n[combined evidence truncated to {max_chars} chars]"
    manifest = {
        "label": label,
        "source_type": source_type,
        "result_path": str(result_path),
        "job_dir": str(job_dir) if job_dir else None,
        "rollout_id": data.get("rollout_id"),
        "method_id": data.get("method_id"),
        "sources": sources,
    }
    return source_type, context, manifest


def load_evidence_bundle_detailed(
    entries: list[tuple[str, Path]] | None,
    *,
    fallback: Path | None = None,
    total_chars: int = 64000,
) -> tuple[str, str, dict[str, Any]]:
    """Build the exact diagnosis evidence plus a hash-addressed source manifest."""
    cleaned: list[tuple[str, Path]] = []
    for label, path in entries or []:
        if path is None:
            continue
        candidate = Path(path)
        if candidate.is_file():
            cleaned.append((str(label), candidate))
    if not cleaned and fallback is not None and Path(fallback).is_file():
        cleaned = [("baseline", Path(fallback))]
    if not cleaned:
        message = "No baseline/gate evidence JSON was found for this task in the current run."
        return "mixed", message, {"entries": [], "model_context": message, "total_chars": len(message)}

    per = max(12000, total_chars // len(cleaned))
    parts: list[str] = []
    types: list[str] = []
    manifests: list[dict[str, Any]] = []
    for label, path in cleaned:
        source_type, ctx, manifest = _detailed_result_context(
            label=label,
            result_path=path,
            max_chars=per,
        )
        types.append(source_type)
        manifests.append(manifest)
        parts.append(f"### Evidence: {label} ({source_type})\n{ctx}")
    if all(item == "failure" for item in types):
        bundle_type = "failure"
    elif all(item == "success" for item in types):
        bundle_type = "success"
    else:
        bundle_type = "mixed"
    header = (
        f"Accumulated execution evidence ({len(cleaned)} source rollout(s)). "
        "The excerpts below come from the actual agent trajectory and verifier artifacts. "
        "Later repair rounds must use every prior task failure and must distinguish "
        "agent/skill failures from infrastructure failures.\n\n"
    )
    context = header + "\n\n".join(parts)
    return bundle_type, context, {
        "entries": manifests,
        "model_context": context,
        "total_chars": len(context),
        "context_limit_chars": total_chars,
    }


def load_evidence_bundle(
    entries: list[tuple[str, Path]] | None,
    *,
    fallback: Path | None = None,
    total_chars: int = 24000,
) -> tuple[str, str]:
    """Compatibility wrapper returning only source type and model context."""
    bundle_type, context, _manifest = load_evidence_bundle_detailed(
        entries,
        fallback=fallback,
        total_chars=total_chars,
    )
    return bundle_type, context


@contextmanager
def import_from_method_repo(method_root: Path):
    method_root = method_root.resolve()
    old_path = list(sys.path)
    old_modules = {name: module for name, module in sys.modules.items() if name == "skillopt" or name.startswith("skillopt.")}
    for name in list(old_modules):
        sys.modules.pop(name, None)
    sys.path.insert(0, str(method_root))
    try:
        yield
    finally:
        for name in [name for name in sys.modules if name == "skillopt" or name.startswith("skillopt.")]:
            sys.modules.pop(name, None)
        sys.modules.update(old_modules)
        sys.path[:] = old_path


def configure_upstream_backend(method_root: Path, lite: bool) -> None:
    configure_model_env()
    with import_from_method_repo(method_root):
        if lite:
            from skillopt.model import set_optimizer_backend, set_target_backend
            from skillopt.model import azure_openai

            set_optimizer_backend("openai_chat")
            set_target_backend("openai_chat")
            azure_openai.configure_azure_openai(
                endpoint=os.environ["SKILLOPT_API_BASE"],
                api_key=os.environ["AI360_API_KEY"],
                auth_mode="openai_compatible",
                optimizer_endpoint=os.environ["SKILLOPT_API_BASE"],
                optimizer_api_key=os.environ["AI360_API_KEY"],
                optimizer_auth_mode="openai_compatible",
            )
        else:
            from skillopt.model import set_optimizer_backend, set_target_backend

            set_optimizer_backend("openai_compatible")
            set_target_backend("openai_compatible")


def _fallback_extract_json(text: str) -> dict[str, Any] | None:
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    candidates = [fence.group(1)] if fence else []
    candidates.append(text)
    for candidate in candidates:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end == -1 or end <= start:
            continue
        try:
            value = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def skill_inventory(bundle_dir: Path) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for skill_file in sorted(bundle_dir.glob("*/SKILL.md")):
        rel = skill_file.relative_to(bundle_dir).as_posix()
        text = skill_file.read_text(encoding="utf-8", errors="replace")
        heading = next((line.lstrip("# ").strip() for line in text.splitlines() if line.startswith("#")), "")
        inventory.append(
            {
                "path": rel,
                "name": skill_file.parent.name,
                "heading": heading,
                "excerpt": short_text(text, 1800),
            }
        )
    return inventory


def _fallback_diagnosis(
    *,
    task_id: str,
    inventory: list[dict[str, Any]],
    reason: str,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "fallback_used": True,
        "fallback_reason": reason,
        "overall_diagnosis": "Diagnosis model output was unavailable or incomplete, so all task skills were conservatively selected.",
        "diagnosed_skills": [
            {
                "path": item["path"],
                "confidence": "fallback",
                "diagnosis": "Selected by conservative fallback because the adapter could not trust a narrower localization result.",
                "repair_instruction": "Improve this skill only when the task context or baseline evidence indicates reusable guidance is missing or ambiguous.",
            }
            for item in inventory
        ],
        "unselected_skills": [],
    }


def _run_diagnosis_llm(
    *,
    method_root: Path,
    lite: bool,
    task_id: str,
    inventory: list[dict[str, Any]],
    task_context: str,
    baseline_source_type: str,
    baseline_context: str,
) -> tuple[dict[str, Any], str, dict[str, Any], float, dict[str, Any]]:
    """Return diagnosis plus the exact optimizer-facing request and response text."""
    configure_model_env()
    system = (
        "You are a SkillOpt diagnostic planner for a single SkillsBench task. "
        "Localize which SKILL.md files should be repaired before evaluation. "
        "Return exactly one valid JSON object and no markdown. "
        "Required keys: overall_diagnosis:string, diagnosed_skills:array, unselected_skills:array. "
        "Each diagnosed_skills item must have path, confidence, diagnosis, and repair_instruction. "
        "Use only paths from the provided skill inventory. If uncertain, select the possibly relevant skill rather than dropping it."
    )
    user = (
        f"## Task ID\n{task_id}\n\n"
        f"## Skill Inventory\n{json.dumps(inventory, ensure_ascii=False, indent=2)}\n\n"
        f"## Task Context\n{task_context}\n\n"
        f"## Baseline Evidence ({baseline_source_type})\n{baseline_context}\n\n"
        "Select the skills that should be repaired for this task. Do not invent paths. "
        "A skill should be selected only if its instructions plausibly contributed to the failure or need task-specific clarification."
    )
    request_record = {
        "stage": "diagnose",
        "provider": os.environ.get("MODEL_PROVIDER", ""),
        "model": os.environ.get("SKILLOPT_MODEL", ""),
        "system": system,
        "user": user,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "parameters": {
            "max_completion_tokens": 12000,
            "retries": 2,
            "reasoning_effort": os.environ.get("BENCHMARK_REASONING_EFFORT", "").strip() or None,
        },
    }
    raw_text = ""
    usage: dict[str, Any] = {}
    started = time.monotonic()
    try:
        if _uses_tatu_messages():
            raw_text, usage = _tatu_messages_chat(
                system=system,
                user=user,
                max_completion_tokens=12000,
                retries=2,
            )
        else:
            with import_from_method_repo(method_root):
                if lite:
                    from skillopt.model import set_optimizer_backend, set_target_backend
                    from skillopt.model import azure_openai

                    set_optimizer_backend("openai_chat")
                    set_target_backend("openai_chat")
                    azure_openai.configure_azure_openai(
                        endpoint=os.environ["SKILLOPT_API_BASE"],
                        api_key=os.environ["AI360_API_KEY"],
                        auth_mode="openai_compatible",
                        optimizer_endpoint=os.environ["SKILLOPT_API_BASE"],
                        optimizer_api_key=os.environ["AI360_API_KEY"],
                        optimizer_auth_mode="openai_compatible",
                    )
                else:
                    from skillopt.model import set_optimizer_backend, set_target_backend

                    set_optimizer_backend("openai_compatible")
                    set_target_backend("openai_compatible")

                from skillopt.model import chat_optimizer

                raw_text, usage = chat_optimizer(
                    system=system,
                    user=user,
                    max_completion_tokens=12000,
                    retries=2,
                    stage="diagnose",
                    reasoning_effort=os.environ.get("BENCHMARK_REASONING_EFFORT", "").strip() or None,
                )
        with import_from_method_repo(method_root):
            from skillopt.utils import extract_json

            parsed = extract_json(raw_text) or _fallback_extract_json(raw_text)
    except Exception as exc:  # noqa: BLE001
        duration = round(time.monotonic() - started, 3)
        diagnosis = _fallback_diagnosis(task_id=task_id, inventory=inventory, reason=repr(exc))
        request_record["error"] = repr(exc)
        return diagnosis, raw_text, usage, duration, request_record

    duration = round(time.monotonic() - started, 3)
    diagnosis = _normalize_parsed_diagnosis(parsed if isinstance(parsed, dict) else None, inventory, task_id)
    return diagnosis, raw_text, usage, duration, request_record


def _normalize_parsed_diagnosis(
    parsed: dict[str, Any] | None,
    inventory: list[dict[str, Any]],
    task_id: str,
) -> dict[str, Any]:
    valid_paths = {item["path"] for item in inventory}
    diagnosed = parsed.get("diagnosed_skills") if isinstance(parsed, dict) else None
    if not isinstance(diagnosed, list):
        return _fallback_diagnosis(task_id=task_id, inventory=inventory, reason="missing diagnosed_skills")
    normalized = []
    seen: set[str] = set()
    for item in diagnosed:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "")).strip()
        if path not in valid_paths or path in seen:
            continue
        seen.add(path)
        normalized.append(
            {
                "path": path,
                "confidence": str(item.get("confidence", "unknown")),
                "diagnosis": str(item.get("diagnosis", "")).strip(),
                "repair_instruction": str(item.get("repair_instruction", "")).strip(),
            }
        )
    if not normalized:
        return _fallback_diagnosis(task_id=task_id, inventory=inventory, reason="no valid selected skill paths")
    return {
        "task_id": task_id,
        "fallback_used": False,
        "overall_diagnosis": str(parsed.get("overall_diagnosis", "")).strip() if isinstance(parsed, dict) else "",
        "diagnosed_skills": normalized,
        "unselected_skills": [item["path"] for item in inventory if item["path"] not in seen],
    }


def _configure_optimizer_backend(*, method_root: Path, lite: bool) -> None:
    configure_model_env()
    with import_from_method_repo(method_root):
        if lite:
            from skillopt.model import set_optimizer_backend, set_target_backend
            from skillopt.model import azure_openai

            set_optimizer_backend("openai_chat")
            set_target_backend("openai_chat")
            azure_openai.configure_azure_openai(
                endpoint=os.environ["SKILLOPT_API_BASE"],
                api_key=os.environ["AI360_API_KEY"],
                auth_mode="openai_compatible",
                optimizer_endpoint=os.environ["SKILLOPT_API_BASE"],
                optimizer_api_key=os.environ["AI360_API_KEY"],
                optimizer_auth_mode="openai_compatible",
            )
        else:
            from skillopt.model import set_optimizer_backend, set_target_backend

            set_optimizer_backend("openai_compatible")
            set_target_backend("openai_compatible")


def _merge_via_optimizer(
    *,
    method_root: Path,
    lite: bool,
    samples: list[dict[str, Any]],
    inventory: list[dict[str, Any]],
    task_id: str,
    budget_l: int,
    rejected_buffer: list[dict[str, Any]] | None = None,
    capture: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], str, dict[str, Any], float]:
    if not _uses_tatu_messages():
        _configure_optimizer_backend(method_root=method_root, lite=lite)

    def chat_fn(*, system: str, user: str) -> tuple[str, dict[str, Any]]:
        if _uses_tatu_messages():
            return _tatu_messages_chat(
                system=system,
                user=user,
                max_completion_tokens=12000,
                retries=2,
            )
        with import_from_method_repo(method_root):
            if lite:
                from skillopt.model import set_optimizer_backend, set_target_backend
                from skillopt.model import azure_openai

                set_optimizer_backend("openai_chat")
                set_target_backend("openai_chat")
                azure_openai.configure_azure_openai(
                    endpoint=os.environ["SKILLOPT_API_BASE"],
                    api_key=os.environ["AI360_API_KEY"],
                    auth_mode="openai_compatible",
                    optimizer_endpoint=os.environ["SKILLOPT_API_BASE"],
                    optimizer_api_key=os.environ["AI360_API_KEY"],
                    optimizer_auth_mode="openai_compatible",
                )
            else:
                from skillopt.model import set_optimizer_backend, set_target_backend

                set_optimizer_backend("openai_compatible")
                set_target_backend("openai_compatible")
            from skillopt.model import chat_optimizer

            return chat_optimizer(
                system=system,
                user=user,
                max_completion_tokens=12000,
                retries=2,
                stage="reflect_merge",
                reasoning_effort=os.environ.get("BENCHMARK_REASONING_EFFORT", "").strip() or None,
            )

    with import_from_method_repo(method_root):
        from skillopt.utils import extract_json

        return merge_diagnosis_samples(
            samples=samples,
            inventory=inventory,
            task_id=task_id,
            budget_l=budget_l,
            chat_fn=chat_fn,
            extract_json_fn=extract_json,
            fallback_extract_fn=_fallback_extract_json,
            normalize_fn=_normalize_parsed_diagnosis,
            rejected_buffer=rejected_buffer,
            capture=capture,
        )


def _produce_diagnosis_with_n_samples(
    *,
    method_root: Path,
    lite: bool,
    task_id: str,
    inventory: list[dict[str, Any]],
    task_context: str,
    baseline_source_type: str,
    baseline_context: str,
    workspace: Path,
    merge_samples: bool = True,
    budget_l: int | None = None,
    rejected_buffer: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], str, dict[str, Any], float, list[dict[str, Any]]]:
    n = diagnosis_sample_count()
    budget = budget_l if budget_l is not None else edit_budget_l()

    def runner() -> tuple[dict[str, Any], str, dict[str, Any], float, dict[str, Any]]:
        return _run_diagnosis_llm(
            method_root=method_root,
            lite=lite,
            task_id=task_id,
            inventory=inventory,
            task_context=task_context,
            baseline_source_type=baseline_source_type,
            baseline_context=baseline_context,
        )

    results = run_diagnosis_samples(n=n, runner=runner, parallel=diagnosis_parallel())
    samples = [item[0] for item in results]
    samples_dir = workspace / "diagnosis_samples"
    samples_dir.mkdir(parents=True, exist_ok=True)
    for idx, (diag, raw_text, usage, duration, request_record) in enumerate(results, start=1):
        write_json(
            samples_dir / f"sample_{idx}.json",
            {
                "request": request_record,
                "diagnosis": diag,
                "response": {
                    "raw_text": raw_text,
                    "usage": usage,
                    "duration_sec": duration,
                },
            },
        )

    if n == 1 or not merge_samples:
        if n == 1:
            diagnosis = truncate_diagnosed_skills(dict(samples[0]), budget)
            diagnosis["diagnosis_sample_count"] = 1
            diagnosis["merged_from_samples"] = False
            diagnosis["edit_budget_l"] = budget
            _diag, raw_text, usage, duration, _request_record = results[0]
            return diagnosis, raw_text, usage, duration, samples
        diagnosis = pick_loose_diagnosis(samples, budget_l=budget)
        return diagnosis, "", {}, 0.0, samples

    merge_capture: dict[str, Any] = {}
    merged, raw_text, usage, duration = _merge_via_optimizer(
        method_root=method_root,
        lite=lite,
        samples=samples,
        inventory=inventory,
        task_id=task_id,
        budget_l=budget,
        rejected_buffer=rejected_buffer,
        capture=merge_capture,
    )
    if merge_capture:
        merge_capture["model"] = os.environ.get("SKILLOPT_MODEL", "")
        merge_capture["provider"] = os.environ.get("MODEL_PROVIDER", "")
        write_json(workspace / "diagnosis_merge.json", merge_capture)
    return merged, raw_text, usage, duration, samples


def _write_diagnosis_artifacts(
    *,
    diagnosis: dict[str, Any],
    raw_text: str,
    usage: dict[str, Any],
    duration: float,
    parsed_keys: list[str],
    raw_log_path: Path,
    parsed_path: Path,
) -> None:
    write_json(
        raw_log_path,
        {
            "ok": not diagnosis.get("fallback_used", False),
            "raw_text": raw_text,
            "usage": usage,
            "duration_sec": duration,
            "parsed_keys": parsed_keys,
            "shared": bool(diagnosis.get("shared_diagnosis")),
            "shared_source": diagnosis.get("shared_diagnosis_source"),
        },
    )
    write_json(parsed_path, diagnosis)


def diagnose_skills_once(
    *,
    method_name: str,
    method_root: Path,
    lite: bool,
    task_id: str,
    workspace: Path,
    inventory: list[dict[str, Any]],
    task_context: str,
    baseline_source_type: str,
    baseline_context: str,
    run_id: str | None = None,
    repair_round: int = 1,
    merge_samples: bool = True,
    budget_l: int | None = None,
    rejected_buffer: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not inventory:
        raise FileNotFoundError("No SKILL.md files found in the task skill bundle.")

    workspace.mkdir(parents=True, exist_ok=True)
    raw_log_path = workspace / "diagnosis_raw.json"
    parsed_path = workspace / "diagnosis.json"
    # Skip shared cache when rejected buffer is non-empty — merge/prompt depends on it.
    use_shared = (
        bool(run_id)
        and _env_flag("SKILLOPT_EVA_SHARED_DIAGNOSIS", True)
        and not (rejected_buffer)
    )
    effective_budget = budget_l if budget_l is not None else edit_budget_l()

    def _finalize(diagnosis: dict[str, Any], raw_text: str, usage: dict[str, Any], duration: float, *, shared: bool, source: str) -> dict[str, Any]:
        diagnosis = dict(diagnosis)
        diagnosis["shared_diagnosis"] = shared
        diagnosis["shared_diagnosis_source"] = source if shared else None
        diagnosis["consumer_method"] = method_name
        diagnosis["repair_round"] = repair_round
        diagnosis["diagnosis_n"] = diagnosis.get("diagnosis_sample_count") or diagnosis_sample_count()
        diagnosis["edit_budget_l"] = diagnosis.get("edit_budget_l") or effective_budget
        diagnosis["merge_samples"] = merge_samples
        return diagnosis

    produce_kwargs = dict(
        task_id=task_id,
        inventory=inventory,
        task_context=task_context,
        baseline_source_type=baseline_source_type,
        baseline_context=baseline_context,
        workspace=workspace,
        merge_samples=merge_samples,
        budget_l=effective_budget,
        rejected_buffer=rejected_buffer,
    )

    if use_shared:
        assert run_id is not None
        shared_dir = shared_diagnosis_dir(run_id, task_id, repair_round=repair_round, method_name=method_name)
        shared_dir.mkdir(parents=True, exist_ok=True)
        shared_diag = shared_dir / "diagnosis.json"
        shared_raw = shared_dir / "diagnosis_raw.json"
        lock_path = shared_dir / "diagnosis.lock"

        with lock_path.open("a+", encoding="utf-8") as lock_fh:
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
            if shared_diag.is_file():
                diagnosis = _finalize(
                    json.loads(shared_diag.read_text(encoding="utf-8")),
                    "",
                    {},
                    0.0,
                    shared=True,
                    source="cache",
                )
                if shared_raw.is_file():
                    shutil.copy2(shared_raw, raw_log_path)
                else:
                    write_json(
                        raw_log_path,
                        {
                            "ok": not diagnosis.get("fallback_used", False),
                            "shared": True,
                            "shared_source": "cache",
                            "note": "Reused shared diagnosis; raw log was missing.",
                        },
                    )
                write_json(parsed_path, diagnosis)
                return diagnosis

            diagnosis, raw_text, usage, duration, _samples = _produce_diagnosis_with_n_samples(
                method_root=method_root,
                lite=lite,
                **produce_kwargs,
            )
            diagnosis = _finalize(diagnosis, raw_text, usage, duration, shared=True, source="fresh")
            diagnosis["producer_backend"] = method_name
            shared_payload = {k: v for k, v in diagnosis.items() if k != "consumer_method"}
            _write_diagnosis_artifacts(
                diagnosis=shared_payload,
                raw_text=raw_text,
                usage=usage,
                duration=duration,
                parsed_keys=sorted(shared_payload.keys()),
                raw_log_path=shared_raw,
                parsed_path=shared_diag,
            )
            if shared_raw.is_file():
                shutil.copy2(shared_raw, raw_log_path)
            write_json(parsed_path, diagnosis)
            return diagnosis

    diagnosis, raw_text, usage, duration, _samples = _produce_diagnosis_with_n_samples(
        method_root=method_root,
        lite=lite,
        **produce_kwargs,
    )
    diagnosis = _finalize(diagnosis, raw_text, usage, duration, shared=False, source="")
    _write_diagnosis_artifacts(
        diagnosis=diagnosis,
        raw_text=raw_text,
        usage=usage,
        duration=duration,
        parsed_keys=sorted(diagnosis.keys()),
        raw_log_path=raw_log_path,
        parsed_path=parsed_path,
    )
    return diagnosis



def rewrite_one_skill(
    *,
    method_root: Path,
    lite: bool,
    skill_content: str,
    suggestion: dict[str, Any],
    raw_log_path: Path,
) -> dict[str, Any]:
    configure_model_env()
    raw_log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    raw_text = ""
    usage: dict[str, Any] = {}
    result: dict[str, Any] | None = None
    request_record: dict[str, Any] = {}
    # Tatu's Claude deployment exposes Anthropic Messages, while the upstream
    # SkillOpt rewrite helper is wired to OpenAI Chat Completions. Use the same
    # adapter-level Messages call as diagnosis/merge for this provider.
    use_upstream = _env_flag("SKILLOPT_EVA_USE_UPSTREAM_REWRITE", True) and not _uses_tatu_messages()

    with import_from_method_repo(method_root):
        if lite:
            from skillopt.model import set_optimizer_backend, set_target_backend
            from skillopt.model import azure_openai

            set_optimizer_backend("openai_chat")
            set_target_backend("openai_chat")
            azure_openai.configure_azure_openai(
                endpoint=os.environ["SKILLOPT_API_BASE"],
                api_key=os.environ["AI360_API_KEY"],
                auth_mode="openai_compatible",
                optimizer_endpoint=os.environ["SKILLOPT_API_BASE"],
                optimizer_api_key=os.environ["AI360_API_KEY"],
                optimizer_auth_mode="openai_compatible",
            )
        else:
            from skillopt.model import set_optimizer_backend, set_target_backend

            set_optimizer_backend("openai_compatible")
            set_target_backend("openai_compatible")

        reasoning_effort = os.environ.get("BENCHMARK_REASONING_EFFORT", "").strip() or "high"
        try:
            if use_upstream:
                from skillopt.optimizer.rewrite import rewrite_skill_from_suggestions

                patch = {"revise_suggestions": [suggestion]}
                request_record = {
                    "stage": "rewrite",
                    "transport": "upstream_skillopt_helper",
                    "model": os.environ.get("SKILLOPT_MODEL", ""),
                    "skill_content": skill_content,
                    "patch": patch,
                    "parameters": {
                        "reasoning_effort": reasoning_effort,
                        "max_completion_tokens": 24000,
                    },
                }
                result = rewrite_skill_from_suggestions(
                    skill_content,
                    patch,
                    reasoning_effort=reasoning_effort,
                    max_completion_tokens=24000,
                )
            else:
                from skillopt.model import chat_optimizer
                from skillopt.prompts import load_prompt
                from skillopt.utils import extract_json

                system = (
                    f"{load_prompt('rewrite_skill')}\n\n"
                    "Output contract for this adapter: return exactly one valid JSON object and no markdown. "
                    "The object must have string key `new_skill`, array key `change_summary`, and string key `reasoning`. "
                    "Make `reasoning` brief. Put the complete rewritten SKILL.md text in `new_skill`."
                )
                user = (
                    f"## Current Skill\n{skill_content}\n\n"
                    "## Selected Revise Suggestions (1 total)\n"
                    f"{json.dumps([suggestion], ensure_ascii=False, indent=2)}\n\n"
                    "Rewrite the full skill document so it integrates the selected suggestions. "
                    "Return ONLY valid JSON with keys `reasoning`, `change_summary`, and `new_skill`. "
                    "The `new_skill` value must contain the complete new skill document."
                )
                request_record = {
                    "stage": "rewrite",
                    "transport": "adapter_chat",
                    "provider": os.environ.get("MODEL_PROVIDER", ""),
                    "model": os.environ.get("SKILLOPT_MODEL", ""),
                    "system": system,
                    "user": user,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "parameters": {
                        "max_completion_tokens": 24000,
                        "retries": 2,
                        "reasoning_effort": reasoning_effort,
                    },
                }
                if _uses_tatu_messages():
                    raw_text, usage = _tatu_messages_chat(
                        system=system,
                        user=user,
                        max_completion_tokens=24000,
                        retries=2,
                    )
                else:
                    raw_text, usage = chat_optimizer(
                        system=system,
                        user=user,
                        max_completion_tokens=24000,
                        retries=2,
                        stage="rewrite",
                        reasoning_effort=reasoning_effort,
                    )
                result = extract_json(raw_text) or _fallback_extract_json(raw_text)
        except Exception as exc:  # noqa: BLE001
            write_json(
                raw_log_path,
                {
                    "ok": False,
                    "error": repr(exc),
                    "request": request_record,
                    "response": {"raw_text": raw_text, "usage": usage},
                    "usage": usage,
                    "duration_sec": round(time.monotonic() - started, 3),
                    "upstream_rewrite": use_upstream,
                },
            )
            raise

    write_json(
        raw_log_path,
        {
            "ok": bool(result and str(result.get("new_skill", "")).strip()),
            "request": request_record,
            "response": {
                "raw_text": raw_text,
                "parsed": result,
                "usage": usage,
            },
            "duration_sec": round(time.monotonic() - started, 3),
            "parsed_keys": sorted(result.keys()) if isinstance(result, dict) else [],
            "upstream_rewrite": use_upstream,
        },
    )
    if not result or not str(result.get("new_skill", "")).strip():
        raise RuntimeError(f"Rewrite response did not contain new_skill; see {raw_log_path}")
    result["new_skill"] = str(result["new_skill"]).rstrip() + "\n"
    if not isinstance(result.get("change_summary"), list):
        result["change_summary"] = []
    return result


def build_suggestion(
    *,
    task_id: str,
    skill_rel: Path,
    task_context: str,
    baseline_source_type: str,
    baseline_context: str,
    diagnosis_item: dict[str, Any] | None = None,
    method_name: str | None = None,
) -> dict[str, Any]:
    # Route B: SO/Lite share the same suggestion text. method_name is kept for
    # call-site compatibility but must not change rewrite instructions.
    _ = method_name
    diagnosis_item = diagnosis_item or {}
    diagnosis_text = str(diagnosis_item.get("diagnosis", "")).strip() or "No narrower diagnosis was provided."
    repair_instruction = str(diagnosis_item.get("repair_instruction", "")).strip() or "Repair this skill with concise, reusable task guidance."
    confidence = str(diagnosis_item.get("confidence", "unknown")).strip() or "unknown"
    return {
        "type": "clarify",
        "title": f"Per-task SkillsBench update for {task_id}",
        "motivation": "Adapt the shipped skill to the observed single-task execution evidence while keeping the SkillsBench task harness unchanged.",
        "instruction": (
            f"Rewrite only this diagnosed skill document ({skill_rel.as_posix()}) so it better supports task `{task_id}`. "
            f"Diagnosis confidence: {confidence}. Diagnosis: {diagnosis_text} Repair instruction: {repair_instruction} "
            "Use the task statement and baseline execution evidence below. Keep guidance reusable for this task type; "
            "do not insert gold answers, hidden oracle details, exact task IDs as special cases, or brittle file paths unless the original task specification requires those paths. "
            "Prefer concise operational checks, failure-prevention rules, and verification steps that the downstream agent can follow.\n\n"
            f"### Task Context\n{task_context}\n\n"
            f"### Baseline Evidence ({baseline_source_type})\n{baseline_context}"
        ),
        "priority_hint": "high",
        "support_count": 1,
        "source_type": baseline_source_type,
    }


def rewrite_bundle_once(
    *,
    method_name: str,
    method_root: Path,
    lite: bool,
    task_id: str,
    workspace: Path,
    before_skill: Path,
    after_skill: Path,
    baseline_result: Path | None,
    run_id: str | None = None,
    repair_round: int = 1,
    allow_overwrite: bool = False,
    rejected_buffer: list[dict[str, Any]] | None = None,
    evidence_paths: list[tuple[str, Path]] | None = None,
) -> dict[str, Any]:
    if after_skill.exists():
        if not allow_overwrite:
            raise FileExistsError(f"Refusing to overwrite existing generated bundle: {after_skill}")
        shutil.rmtree(after_skill)
    shutil.copytree(before_skill, after_skill, symlinks=False)
    workspace.mkdir(parents=True, exist_ok=True)
    if not run_id:
        run_id = infer_run_id_from_workspace(workspace)

    profile = method_profile(method_name)
    budget = max(1, int(edit_budget_l() * float(profile.get("budget_multiplier") or 1.0)))
    update_mode = str(profile.get("update_mode") or "patch")

    configure_model_env()
    task_context = load_task_context(task_id)
    baseline_source_type, baseline_context, evidence_manifest = load_evidence_bundle_detailed(
        evidence_paths,
        fallback=baseline_result,
    )
    write_json(
        workspace / "evidence_bundle.json",
        {
            "repair_round": repair_round,
            "source_type": baseline_source_type,
            "entries": evidence_manifest.get("entries", []),
            "context_chars": len(baseline_context),
            "context_limit_chars": evidence_manifest.get("context_limit_chars"),
            "model_context": baseline_context,
        },
    )
    inventory = skill_inventory(before_skill)
    diagnosis = diagnose_skills_once(
        method_name=method_name,
        method_root=method_root,
        lite=lite,
        task_id=task_id,
        workspace=workspace,
        inventory=inventory,
        task_context=task_context,
        baseline_source_type=baseline_source_type,
        baseline_context=baseline_context,
        run_id=run_id,
        repair_round=repair_round,
        merge_samples=bool(profile.get("merge_samples", True)),
        budget_l=budget,
        rejected_buffer=rejected_buffer,
    )
    diagnosed_by_path = {
        str(item["path"]): item
        for item in diagnosis.get("diagnosed_skills", [])
        if isinstance(item, dict) and item.get("path")
    }
    manifest: dict[str, Any] = {
        "method": method_name,
        "method_root": str(method_root),
        "task_id": task_id,
        "run_id": run_id,
        "repair_round": repair_round,
        "method_profile": profile,
        "smoke_mode": smoke_mode(),
        "same_task_gate_note": "Acceptance uses the same task (not held-out val).",
        "route_b": {
            "shared_diagnosis": bool(diagnosis.get("shared_diagnosis")),
            "shared_diagnosis_source": diagnosis.get("shared_diagnosis_source"),
            "neutral_suggestion": True,
            "upstream_rewrite": _env_flag("SKILLOPT_EVA_USE_UPSTREAM_REWRITE", True)
            and not _uses_tatu_messages(),
            "diagnosis_n": diagnosis_sample_count(),
            "edit_budget_l": budget,
            "repair_rounds_r": repair_rounds_r(bonus=int(profile.get("repair_rounds_bonus") or 0)),
            "update_mode": update_mode,
            "merge_samples": bool(profile.get("merge_samples", True)),
        },
        "optimizer_model": os.environ.get("SKILLOPT_MODEL", ""),
        "baseline_result": str(baseline_result) if baseline_result else None,
        "evidence_paths": [
            {"label": label, "path": str(path)}
            for label, path in (evidence_paths or [])
            if path is not None
        ],
        "rejected_buffer_size": len(rejected_buffer or []),
        "diagnosis": diagnosis,
        "skill_inventory": [{k: item[k] for k in ("path", "name", "heading") if k in item} for item in inventory],
        "rewritten_files": [],
        "unmodified_files": [item["path"] for item in inventory if item["path"] not in diagnosed_by_path],
    }

    for rel_text, diagnosis_item in sorted(diagnosed_by_path.items()):
        rel = Path(rel_text)
        skill_file = after_skill / rel
        before_file = before_skill / rel
        if not before_file.is_file():
            raise FileNotFoundError(f"Diagnosed skill path is not in original bundle: {rel_text}")
        skill_content = before_file.read_text(encoding="utf-8", errors="replace")
        suggestion = build_suggestion(
            method_name=method_name,
            task_id=task_id,
            skill_rel=rel,
            task_context=task_context,
            baseline_source_type=baseline_source_type,
            baseline_context=baseline_context,
            diagnosis_item=diagnosis_item,
        )
        safe_name = rel.as_posix().replace("/", "__")
        raw_log_path = workspace / "rewrite_raw" / f"{safe_name}.json"

        def _rewrite_fn() -> dict[str, Any]:
            return rewrite_one_skill(
                method_root=method_root,
                lite=lite,
                skill_content=skill_content,
                suggestion=suggestion,
                raw_log_path=raw_log_path.with_name(raw_log_path.stem + "__full_rewrite.json"),
            )

        def _propose_chat(*, system: str, user: str) -> tuple[str, dict[str, Any]]:
            if _uses_tatu_messages():
                return _tatu_messages_chat(
                    system=system,
                    user=user,
                    max_completion_tokens=12000,
                    retries=2,
                )
            with import_from_method_repo(method_root):
                if lite:
                    from skillopt.model import set_optimizer_backend, set_target_backend
                    from skillopt.model import azure_openai

                    set_optimizer_backend("openai_chat")
                    set_target_backend("openai_chat")
                    azure_openai.configure_azure_openai(
                        endpoint=os.environ["SKILLOPT_API_BASE"],
                        api_key=os.environ["AI360_API_KEY"],
                        auth_mode="openai_compatible",
                        optimizer_endpoint=os.environ["SKILLOPT_API_BASE"],
                        optimizer_api_key=os.environ["AI360_API_KEY"],
                        optimizer_auth_mode="openai_compatible",
                    )
                else:
                    from skillopt.model import set_optimizer_backend, set_target_backend

                    set_optimizer_backend("openai_compatible")
                    set_target_backend("openai_compatible")
                from skillopt.model import chat_optimizer

                return chat_optimizer(
                    system=system,
                    user=user,
                    max_completion_tokens=12000,
                    retries=2,
                    stage="bounded_edit",
                    reasoning_effort=os.environ.get("BENCHMARK_REASONING_EFFORT", "").strip() or None,
                )

        with import_from_method_repo(method_root):
            from skillopt.utils import extract_json

            result = patch_skill_with_fallback_rewrite(
                skill_content=skill_content,
                skill_path=rel.as_posix(),
                task_id=task_id,
                diagnosis_item=diagnosis_item,
                task_context=task_context,
                baseline_source_type=baseline_source_type,
                baseline_context=baseline_context,
                budget_l=budget,
                update_mode=update_mode,
                rejected_buffer=rejected_buffer,
                propose_chat_fn=_propose_chat,
                extract_json_fn=extract_json,
                fallback_extract_fn=_fallback_extract_json,
                rewrite_fn=_rewrite_fn,
                raw_log_path=raw_log_path,
                write_json_fn=write_json,
            )

        new_skill = str(result["new_skill"]).rstrip() + "\n"
        skill_file.write_text(new_skill, encoding="utf-8")
        manifest["rewritten_files"].append(
            {
                "path": rel.as_posix(),
                "diagnosis": diagnosis_item.get("diagnosis", ""),
                "repair_instruction": diagnosis_item.get("repair_instruction", ""),
                "confidence": diagnosis_item.get("confidence", "unknown"),
                "suggestion": suggestion,
                "change_summary": result.get("change_summary", []),
                "reasoning": result.get("reasoning", ""),
                "update_mode_used": result.get("update_mode_used"),
                "edit_reports": result.get("edit_reports", []),
                "proposed_edits": result.get("proposed_edits", []),
                "fallback_reason": result.get("fallback_reason"),
            }
        )

    write_json(workspace / "optimization_manifest.json", manifest)
    return manifest
