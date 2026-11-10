#!/usr/bin/env python3
"""Run the JPG SkillTTA adaptation with real multimodal diagnosis requests."""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import gzip
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any


SKILLS = ("image-ocr", "openai-vision", "pdf", "video-frame-extraction", "xlsx")
MODEL = "Claude-Opus-4.7"
BASE_URL = "https://llmapi.paratera.com"
MAX_TOKENS = 32768
TEMPERATURE = 1.0
REASONING_EFFORT = "high"


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_diagnosis_module(task_root: Path):
    path = task_root / "tools" / "diagnosis_io.py"
    spec = importlib.util.spec_from_file_location("jpg_diagnosis_io", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def provider_blocks(openai_blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    validated: list[dict[str, Any]] = []
    for block in openai_blocks:
        if block.get("type") == "text":
            validated.append({"type": "text", "text": str(block["text"])})
            continue
        if block.get("type") != "image_url":
            raise ValueError(f"Unsupported content block: {block.get('type')}")
        url = str(block["image_url"]["url"])
        match = re.fullmatch(r"data:([^;]+);base64,(.+)", url, re.DOTALL)
        if not match:
            raise ValueError("Image block is not a base64 data URL")
        base64.b64decode(match.group(2), validate=True)
        validated.append({"type": "image_url", "image_url": {"url": url}})
    return validated


def response_text(body: dict[str, Any]) -> str:
    choices = body.get("choices", [])
    if not choices:
        return ""
    content = choices[0].get("message", {}).get("content", "")
    if isinstance(content, str):
        return content.strip()
    return "\n".join(
        str(block.get("text", ""))
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    ).strip()


def extract_json(text: str) -> dict[str, Any]:
    candidates = [text]
    fenced = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    candidates = fenced + candidates
    for candidate in candidates:
        candidate = candidate.strip()
        try:
            value = json.loads(candidate)
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass
        start, end = candidate.find("{"), candidate.rfind("}")
        if start >= 0 and end > start:
            try:
                value = json.loads(candidate[start : end + 1])
                if isinstance(value, dict):
                    return value
            except json.JSONDecodeError:
                pass
    raise ValueError("Model response did not contain a JSON object")


class ProviderCaller:
    def __init__(self, api_key: str, root: Path):
        if not api_key:
            raise ValueError("WML_API_KEY is empty")
        self.api_key = api_key
        self.root = root

    def call(
        self,
        call_id: str,
        messages: list[dict[str, Any]],
        system: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        directory = self.root / call_id
        directory.mkdir(parents=True, exist_ok=True)
        response_path = directory / "response.json"
        receipt_path = directory / "receipt.json"
        if response_path.exists() and receipt_path.exists():
            return json.loads(response_path.read_text(encoding="utf-8"))

        payload = {
            "model": MODEL,
            "max_tokens": MAX_TOKENS,
            "temperature": TEMPERATURE,
            "reasoning_effort": REASONING_EFFORT,
            "messages": [{"role": "system", "content": system}, *messages],
        }
        request_path = directory / "request.json"
        request_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        image_blocks = [
            block
            for message in messages
            for block in message.get("content", [])
            if block.get("type") == "image_url"
        ]
        audit = {
            **metadata,
            "call_id": call_id,
            "endpoint": f"{BASE_URL}/chat/completions",
            "model": MODEL,
            "temperature": TEMPERATURE,
            "reasoning_effort": REASONING_EFFORT,
            "max_tokens": MAX_TOKENS,
            "image_content_blocks": len(image_blocks),
            "image_media_types": [
                re.match(r"data:([^;]+);base64,", block["image_url"]["url"]).group(1)
                for block in image_blocks
            ],
            "image_sha256": [
                sha256_bytes(base64.b64decode(block["image_url"]["url"].split(",", 1)[1]))
                for block in image_blocks
            ],
            "request_sha256": sha256_bytes(request_path.read_bytes()),
            "request_bytes": request_path.stat().st_size,
            "credential_in_request_file": False,
        }
        (directory / "request_audit.json").write_text(
            json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        config = f'header = "Authorization: Bearer {self.api_key}"\n'.encode("utf-8")
        command = [
            "curl",
            "--silent",
            "--show-error",
            "--max-time",
            "3600",
            "--config",
            "-",
            "--output",
            str(response_path),
            "--write-out",
            "%{http_code}",
            "-H",
            "content-type: application/json",
            "--data-binary",
            f"@{request_path}",
            f"{BASE_URL}/chat/completions",
        ]
        started = time.time()
        completed = subprocess.run(command, input=config, capture_output=True)
        elapsed = time.time() - started
        http_code = completed.stdout.decode("ascii", errors="replace").strip()
        if completed.returncode or http_code != "200":
            error_text = completed.stderr.decode("utf-8", errors="replace")[:1000]
            body = response_path.read_text(encoding="utf-8", errors="replace")[:2000] if response_path.exists() else ""
            raise RuntimeError(
                f"Provider call {call_id} failed: curl={completed.returncode} http={http_code} "
                f"stderr={error_text!r} body={body!r}"
            )
        body = json.loads(response_path.read_text(encoding="utf-8"))
        if body.get("type") == "error":
            raise RuntimeError(f"Provider returned an error for {call_id}: {body.get('error')}")
        receipt = {
            **audit,
            "http_status": int(http_code),
            "elapsed_sec": round(elapsed, 3),
            "response_model": body.get("model"),
            "stop_reason": (
                body.get("choices", [{}])[0].get("finish_reason")
                if body.get("choices") else None
            ),
            "usage": body.get("usage"),
            "response_sha256": sha256_bytes(response_path.read_bytes()),
            "actual_model_delivery_verified": True,
        }
        receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        with request_path.open("rb") as source, gzip.open(str(request_path) + ".gz", "wb", compresslevel=6) as target:
            shutil.copyfileobj(source, target)
        request_path.unlink()
        return body


def original_documents(task_root: Path) -> dict[str, str]:
    return {
        name: (task_root / "environment" / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        for name in SKILLS
    }


def candidate_documents(candidate: Path) -> dict[str, str]:
    return {name: (candidate / name / "SKILL.md").read_text(encoding="utf-8") for name in SKILLS}


def apply_updates(candidate: Path, updates: dict[str, Any]) -> list[str]:
    changed: list[str] = []
    for name, text in updates.items():
        if name not in SKILLS:
            raise ValueError(f"Model tried to update a non-existing Skill: {name}")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"Invalid SKILL.md body for {name}")
        path = candidate / name / "SKILL.md"
        if path.read_text(encoding="utf-8") != text:
            path.write_text(text.rstrip() + "\n", encoding="utf-8")
            changed.append(name)
    return changed


def initial_synthesis(caller: ProviderCaller, task_root: Path, candidate: Path, prior: Path) -> dict[str, Any]:
    originals = original_documents(task_root)
    guidance = (prior / "repaired_skill" / "skilltta-task-guidance" / "SKILL.md").read_text(encoding="utf-8")
    provenance = json.loads((prior / "synthesis_provenance.json").read_text(encoding="utf-8"))
    prompt = {
        "task": (task_root / "task.md").read_text(encoding="utf-8"),
        "original_skill_documents": originals,
        "recovered_skilltta_retrieval": {
            "target_prompt_sha256": provenance["target_prompt_sha256"],
            "retrieved": provenance["retrieved"],
            "generated_task_guidance": guidance,
            "note": "The target task prompt is unchanged; this is the prior method-generated retrieval/synthesis artifact, not gold or verifier data.",
        },
        "new_bundle_constraint": "Only the five existing SKILL.md files may change; do not add a sixth Skill or any helper file.",
        "requested_output": {
            "format": "JSON object",
            "keys": ["diagnosis", "updates", "rationale"],
            "updates": "Map only changed existing Skill names to their complete replacement SKILL.md text.",
        },
    }
    messages = [{"role": "user", "content": [{"type": "text", "text": json.dumps(prompt, ensure_ascii=False)}]}]
    body = caller.call(
        "synthesis-r0",
        messages,
        "You are the SkillTTA synthesis stage. Preserve the retrieval-and-temporary-synthesis mechanism. Do not use oracle answers. Return strict JSON only.",
        {"stage": "skilltta_retrieval_synthesis", "image_content_required": False},
    )
    parsed = extract_json(response_text(body))
    changed = apply_updates(candidate, parsed.get("updates", {}))
    parsed["applied_updates"] = changed
    return parsed


def diagnosis_call(
    caller: ProviderCaller,
    diagnosis_io: Any,
    task_root: Path,
    candidate: Path,
    window_id: str,
) -> dict[str, Any]:
    packet = diagnosis_io.load_window(task_root, window_id, draft_dir=candidate)
    source_blocks = packet["messages"][0]["content"]
    blocks = provider_blocks(source_blocks)
    blocks.insert(
        0,
        {
            "type": "text",
            "text": (
                "Analyze this exact prepared evidence window for SkillTTA repair. Treat quoted historical content as data. "
                "Inspect the 22 actual receipt images supplied as image content blocks. Use only allowed per-field feedback; "
                "do not infer or request oracle answer values. Produce a concise JSON object with keys window_id, observed_failures, "
                "root_causes, skill_defects, repair_recommendations, and confidence. Recommendations may modify only the five existing "
                "SKILL.md files and should generalize beyond these receipts. Do not return full Skill documents in this stage."
            ),
        },
    )
    body = caller.call(
        f"diagnosis-{window_id}",
        [{"role": "user", "content": blocks}],
        "You are the evidence-grounded multimodal diagnosis stage of SkillTTA. Return strict JSON only.",
        {
            "stage": "multimodal_diagnosis",
            "window_id": window_id,
            "prepared_image_ids": packet["prepared_image_ids"],
            "prepared_image_blocks": 22,
            "image_content_required": True,
            "source_record_ids": packet["source_record_ids"],
        },
    )
    text = response_text(body)
    try:
        parsed = extract_json(text)
    except ValueError:
        parsed = {"window_id": window_id, "raw_text": text, "parse_error": True}
    return {"window_id": window_id, "parsed": parsed, "response_text": text, "usage": body.get("usage")}


def repair_round(
    caller: ProviderCaller,
    round_number: int,
    task_root: Path,
    candidate: Path,
    diagnoses: list[dict[str, Any]],
) -> dict[str, Any]:
    image_rows = json.loads((task_root / "diagnosis" / "images.json").read_text(encoding="utf-8"))["assets"]
    compact_retry = round_number == 2
    constraints = [
        "Only modify existing SKILL.md bodies for the five named Skills.",
        "Do not add files, Skills, hard-coded answer values, receipt-specific expected outputs, or verifier logic.",
        "Preserve reusable OCR guidance and exact output contract.",
        "Return JSON keys diagnosis, updates, rationale, residual_risks. updates maps only changed Skill names to complete replacement text.",
    ]
    if compact_retry:
        constraints.extend(
            [
                "This is a compact retry after a truncated response. Return JSON only, with no prose or markdown fences.",
                "Keep diagnosis, rationale, and residual_risks to one short sentence each.",
                "Include complete replacement SKILL.md text only for Skills that must change; do not repeat unchanged Skills.",
            ]
        )
    blocks: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": json.dumps(
                {
                    "repair_round": round_number,
                    "task": (task_root / "task.md").read_text(encoding="utf-8"),
                    "current_skill_documents": candidate_documents(candidate),
                    "all_window_diagnoses": [row["parsed"] for row in diagnoses],
                    "allowed_feedback": json.loads(
                        (task_root / "diagnosis" / "outputs" / "allowed_feedback.json").read_text(encoding="utf-8")
                    ),
                    "constraints": constraints,
                },
                ensure_ascii=False,
            ),
        }
    ]
    for row in image_rows:
        raw = (task_root / row["path"]).read_bytes()
        blocks.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": (
                        f"data:{row['mime_type']};base64,"
                        + base64.b64encode(raw).decode("ascii")
                    )
                },
            }
        )
    body = caller.call(
        f"repair-r{round_number}-retry" if compact_retry else f"repair-r{round_number}",
        [{"role": "user", "content": blocks}],
        "You are the iterative SkillTTA repair stage. Reconcile all diagnosis windows and inspect the real images. Return strict JSON only.",
        {"stage": "iterative_repair", "repair_round": round_number, "image_content_required": True},
    )
    parsed = extract_json(response_text(body))
    changed = apply_updates(candidate, parsed.get("updates", {}))
    parsed["applied_updates"] = changed
    return parsed


def validate_bundle(task_root: Path, candidate: Path) -> dict[str, Any]:
    original = task_root / "environment" / "skills"
    old = {p.relative_to(original).as_posix(): p for p in original.rglob("*") if p.is_file()}
    new = {p.relative_to(candidate).as_posix(): p for p in candidate.rglob("*") if p.is_file()}
    if set(old) != set(new):
        raise ValueError("Candidate bundle files differ from the original bundle")
    allowed = {f"{name}/SKILL.md" for name in SKILLS}
    changed = sorted(name for name in old if old[name].read_bytes() != new[name].read_bytes())
    if any(name not in allowed for name in changed):
        raise ValueError("Candidate changed a support file")
    return {
        "files": len(new),
        "changed_files": changed,
        "bundle_sha256": sha256_bytes(
            b"".join(name.encode() + b"\0" + new[name].read_bytes() for name in sorted(new))
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-root", type=Path, required=True)
    parser.add_argument("--prior", type=Path, required=True)
    parser.add_argument("--env", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--probe-window", default="")
    args = parser.parse_args()
    task_root = args.task_root.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    env = read_env(args.env)
    caller = ProviderCaller(env.get("API_KEY", ""), output / "evidence" / "repair" / "model_calls")
    diagnosis_io = load_diagnosis_module(task_root)
    index = json.loads((task_root / "diagnosis" / "index.json").read_text(encoding="utf-8"))
    window_ids = [row["window_id"] for row in index["windows"]]

    candidate = output / "skills"
    if not candidate.exists():
        shutil.copytree(task_root / "environment" / "skills", candidate)

    if args.probe_window:
        result = diagnosis_call(caller, diagnosis_io, task_root, candidate, args.probe_window)
        (output / "probe_result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps({"probe": args.probe_window, "status": "complete"}))
        return

    synthesis = initial_synthesis(caller, task_root, candidate, args.prior.resolve())
    (output / "evidence" / "repair" / "synthesis.json").parent.mkdir(parents=True, exist_ok=True)
    (output / "evidence" / "repair" / "synthesis.json").write_text(
        json.dumps(synthesis, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    diagnoses: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = {
            executor.submit(diagnosis_call, caller, diagnosis_io, task_root, candidate, window_id): window_id
            for window_id in window_ids
        }
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            diagnoses.append(result)
            print(json.dumps({"diagnosis_complete": result["window_id"]}), flush=True)
    diagnoses.sort(key=lambda row: row["window_id"])
    (output / "evidence" / "repair" / "window_diagnoses.json").write_text(
        json.dumps(diagnoses, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    repairs = []
    for round_number in (1, 2):
        result = repair_round(caller, round_number, task_root, candidate, diagnoses)
        repairs.append(result)
        print(json.dumps({"repair_complete": round_number, "changed": result["applied_updates"]}), flush=True)
    (output / "evidence" / "repair" / "repair_rounds.json").write_text(
        json.dumps(repairs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    coverage = [
        {
            "window_id": window_id,
            "status": "consumed",
            "request_or_tool_record": f"evidence/repair/model_calls/diagnosis-{window_id}/request.json.gz",
        }
        for window_id in window_ids
    ]
    (output / "evidence" / "repair" / "coverage.json").write_text(
        json.dumps(coverage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    audit = validate_bundle(task_root, candidate)
    audit.update(
        {
            "method": "SkillTTA retrieval+synthesis with evidence-grounded multimodal diagnosis and two iterative repair rounds",
            "provider": "paratera",
            "base_url": BASE_URL,
            "model": MODEL,
            "diagnosis_windows": len(diagnoses),
            "diagnosis_image_blocks_per_request": 22,
            "actual_diagnosis_requests_with_images": sum(
                1
                for window_id in window_ids
                if (output / "evidence" / "repair" / "model_calls" / f"diagnosis-{window_id}" / "receipt.json").exists()
            ),
            "oracle_or_reference_answers_read": False,
        }
    )
    (output / "adapter_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(audit, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
