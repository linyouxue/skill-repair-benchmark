from __future__ import annotations

import os
import shlex
import subprocess
import time
import json
import uuid
import gzip
from pathlib import Path
from dataclasses import dataclass, field
from typing import Protocol

from skillrevise.core.env import env_flag_enabled, set_env_with_legacy
from skillrevise.llm.multimodal import MultimodalPrompt, validate_messages, write_json_gzip


PROXY_ENV_KEYS = {
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
}


@dataclass
class LLMResponse:
    text: str
    latency_seconds: float
    metadata: dict[str, object] = field(default_factory=dict)


class LLMClient(Protocol):
    def complete(self, prompt: str | MultimodalPrompt, *, purpose: str) -> LLMResponse:
        """Return a completion for one SkillRevise prompt."""


class CommandLLMClient:
    """Runs an external LLM command that reads the prompt from stdin.

    This keeps SkillRevise independent from OpenAI, Anthropic, local models, or any
    specific SDK. The command should write the final model response to stdout.
    """

    def __init__(
        self,
        command: str | list[str] | tuple[str, ...],
        *,
        timeout_seconds: int = 600,
        env: dict[str, str] | None = None,
    ) -> None:
        self.command = command
        self.timeout_seconds = timeout_seconds
        self.env = env or {}

    def complete(self, prompt: str | MultimodalPrompt, *, purpose: str) -> LLMResponse:
        argv = shlex.split(self.command) if isinstance(self.command, str) else list(self.command)
        env = os.environ.copy()
        env.update(self.env)
        if _bypass_proxy_enabled(env):
            env = _without_proxy_env(env)
        set_env_with_legacy(env, "SKILL_REVISE_REVISION_LLM_PURPOSE", purpose)
        input_text = prompt
        call_dir = None
        if isinstance(prompt, MultimodalPrompt):
            validate_messages(prompt.messages)
            if not prompt.evidence_root:
                raise ValueError("Multimodal requests require an evidence directory")
            if env.get("SKILL_REVISE_JPG_RESUME_REQUESTS") == "1":
                resumed = _resume_jpg_response(prompt, purpose, env)
                if resumed is not None:
                    return resumed
            call_dir = Path(prompt.evidence_root) / f"{purpose}-{uuid.uuid4().hex}"
            call_dir.mkdir(parents=True)
            write_json_gzip(call_dir / "method_input.json.gz", {
                "purpose": purpose, "context": prompt.context, "messages": prompt.messages,
                "status": "prepared_not_sent",
            })
            env["SKILL_REVISE_LLM_INPUT_FORMAT"] = "messages-v1"
            env["SKILL_REVISE_HTTP_EVIDENCE_DIR"] = str(call_dir)
            input_text = json.dumps({"messages": prompt.messages}, ensure_ascii=True)
        attempts = _positive_int(env.get("SKILL_REVISE_LLM_COMMAND_ATTEMPTS"), default=1)
        delay = _positive_int(env.get("SKILL_REVISE_LLM_COMMAND_RETRY_DELAY_SECONDS"), default=8)
        last_completed = None
        started = time.perf_counter()
        for attempt in range(1, attempts + 1):
            completed = subprocess.run(
                argv,
                input=input_text,
                capture_output=True,
                text=True,
                env=env,
                timeout=self.timeout_seconds,
                encoding="utf-8",
                errors="replace",
            )
            last_completed = completed
            if completed.returncode == 0:
                if call_dir is not None:
                    write_json_gzip(call_dir / "command_result.json.gz", {
                        "returncode": completed.returncode, "stdout": completed.stdout,
                        "stderr": completed.stderr, "attempt": attempt,
                    })
                    if not list(call_dir.glob("*/response.json.gz")):
                        raise RuntimeError("Multimodal command returned without HTTP response evidence; use skillrevise.llm.command")
                latency = round(time.perf_counter() - started, 4)
                return LLMResponse(
                    text=(completed.stdout or "").strip(),
                    latency_seconds=latency,
                    metadata={
                        "command": argv[0],
                        "purpose": purpose,
                        "stderr": (completed.stderr or "").strip(),
                        "attempt": attempt,
                        **({"request_evidence_dir": str(call_dir)} if call_dir else {}),
                    },
                )
            if attempt < attempts:
                time.sleep(delay)
        if call_dir is not None and last_completed is not None:
            write_json_gzip(call_dir / "command_result.json.gz", {
                "returncode": last_completed.returncode, "stdout": last_completed.stdout,
                "stderr": last_completed.stderr, "attempt": attempts,
            })
        assert last_completed is not None
        raise RuntimeError(
            f"LLM command failed for {purpose} after {attempts} attempt(s) "
            f"with exit code {last_completed.returncode}: {(last_completed.stderr or '').strip()}"
        )


class StaticLLMClient:
    """Deterministic test double for LLM-backed components."""

    def __init__(self, responses: list[str] | tuple[str, ...]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, str]] = []

    def complete(self, prompt: str | MultimodalPrompt, *, purpose: str) -> LLMResponse:
        self.calls.append({"purpose": purpose, "prompt": prompt})
        if not self.responses:
            raise RuntimeError(f"No static LLM response left for {purpose}")
        return LLMResponse(text=self.responses.pop(0), latency_seconds=0.0, metadata={"purpose": purpose})


def _resume_jpg_response(prompt, purpose, env):
    """Reuse successful exact requests only for the opt-in JPG interrupted diagnosis."""
    if purpose not in {"bundle_skill_selection", "skill_diagnosis", "skill_revision"} or prompt.context.get("task_id") != "jpg-ocr-stat":
        return None
    from skillrevise.llm.command import load_config
    from skillrevise.llm.multimodal import provider_messages
    config = load_config(env)
    if (config.provider, config.model) not in {("openai", "gpt-5.5"), ("anthropic", "claude-opus-4-7")}:
        return None
    if config.provider == "anthropic":
        suffix = "/messages"
        expected = {"model": config.model, "max_tokens": config.max_tokens,
            "temperature": config.temperature, "system": config.system_prompt,
            "messages": provider_messages(prompt, anthropic=True)}
        if config.effort:
            expected["output_config"] = {"effort": config.effort}
    else:
        suffix = "/chat/completions"
        expected = {"model": config.model, "messages": [
            {"role": "system", "content": config.system_prompt}, *prompt.messages],
            "max_completion_tokens": config.max_tokens}
        if config.effort:
            expected["effort"] = config.effort
        if config.seed is not None:
            expected["seed"] = config.seed
    if config.thinking_mode:
        expected["thinking"] = {"type": config.thinking_mode}
    def read(path):
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    root = Path(prompt.evidence_root)
    for folder in sorted(root.glob(purpose + "-*")):
        result_path = folder / "command_result.json.gz"
        input_path = folder / "method_input.json.gz"
        if not result_path.is_file() or not input_path.is_file():
            continue
        result = read(result_path)
        if result.get("returncode") != 0 or not result.get("stdout", "").strip():
            continue
        saved = read(input_path)
        if saved.get("context") != prompt.context or saved.get("messages") != prompt.messages:
            continue
        for request_path in sorted(folder.glob("*/request.json.gz")):
            response_path = request_path.parent / "response.json.gz"
            request = read(request_path)
            if not response_path.exists() or request.get("payload") != expected:
                continue
            if request.get("url") != config.base_url.rstrip("/") + suffix:
                continue
            if read(response_path).get("http_status") != 200:
                continue
            receipt = root / "resume_receipts" / (uuid.uuid4().hex + ".json.gz")
            write_json_gzip(receipt, {"purpose": purpose, "source_request": str(folder),
                "matching": "exact messages, context, model, URL and generation payload", "new_api_call": False})
            print(f"[JPG resume] Reused {purpose} window={prompt.context.get('window_id')}; no API call.", flush=True)
            return LLMResponse(result["stdout"].strip(), 0.0, {
                "purpose": purpose, "request_evidence_dir": str(folder), "resumed_from_saved_response": True})
    return None


def _bypass_proxy_enabled(env: dict[str, str]) -> bool:
    return env_flag_enabled(env, "SKILL_REVISE_BYPASS_PROXY") or env_flag_enabled(env, "SKILL_REVISE_NO_PROXY")


def _without_proxy_env(env: dict[str, str]) -> dict[str, str]:
    cleaned = {key: value for key, value in env.items() if key not in PROXY_ENV_KEYS}
    set_env_with_legacy(cleaned, "SKILL_REVISE_BYPASS_PROXY", "1")
    return cleaned


def _positive_int(raw: str | None, *, default: int) -> int:
    try:
        value = int(raw) if raw is not None else default
    except ValueError:
        return default
    return value if value > 0 else default
