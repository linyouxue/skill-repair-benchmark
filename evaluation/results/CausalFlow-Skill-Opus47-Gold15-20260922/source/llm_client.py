import os
import json
import hashlib
from typing import Any, Dict, List, Optional
import httpx
from openai import OpenAI
from dotenv import load_dotenv
from pydantic import BaseModel
from schemas import LLMSchemas
from text_processor import convert_text_to_jsonl

load_dotenv()

class LLMClient:

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "anthropic/claude-opus-4.7",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ):

        self.api_key = (
            api_key
            or os.getenv("OPENROUTER_API_KEY")
            or os.getenv("OPENROUTER_SECRET_KEY")
        )
        if not self.api_key:
            raise ValueError(
                "OPENROUTER_API_KEY/OPENROUTER_SECRET_KEY not found."
            )

        self.model = model
        self.temperature = temperature
        if max_tokens is not None and max_tokens < 1:
            raise ValueError("max_tokens must be positive when provided")
        self.max_tokens = max_tokens

        # httpx otherwise prefers ALL_PROXY.  On the experiment host that is
        # a SOCKS endpoint, which requires an optional ``socksio`` dependency,
        # while the same local proxy is already exposed over HTTP(S).  Select
        # the HTTP proxy explicitly so CRS runs do not depend on an undeclared
        # optional package.
        http_proxy = (
            os.getenv("HTTPS_PROXY")
            or os.getenv("https_proxy")
            or os.getenv("HTTP_PROXY")
            or os.getenv("http_proxy")
        )
        http_client = httpx.Client(proxy=http_proxy) if http_proxy else None
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
            http_client=http_client,
        )
        self.usage_calls: List[Dict[str, Any]] = []
        self.usage_totals: Dict[str, Any] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost": 0.0,
        }
        self.structured_attempts: List[Dict[str, Any]] = []

    def _record_usage(
        self,
        response: Any,
        *,
        model: str,
        schema_name: Optional[str] = None,
    ) -> None:
        usage = getattr(response, "usage", None)
        if usage is None:
            return
        if hasattr(usage, "model_dump"):
            raw = usage.model_dump()
        elif isinstance(usage, dict):
            raw = dict(usage)
        else:
            raw = {
                name: getattr(usage, name, None)
                for name in ("prompt_tokens", "completion_tokens", "total_tokens")
            }
        record = {
            "model": model,
            "schema_name": schema_name,
            **raw,
        }
        self.usage_calls.append(record)
        print(json.dumps({"event": "model_call_complete", "call_count": len(self.usage_calls),
                          "model": model, "schema": schema_name,
                          "total_tokens": raw.get("total_tokens")}), flush=True)
        for name in ("prompt_tokens", "completion_tokens", "total_tokens"):
            self.usage_totals[name] += int(raw.get(name) or 0)
        self.usage_totals["cost"] += float(raw.get("cost") or 0.0)

    def generate(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> str:
        messages = []

        if system_message:
            messages.append({
                "role": "system",
                "content": system_message
            })

        messages.append({
            "role": "user",
            "content": prompt
        })

        request: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or self.temperature,
        }
        if self.max_tokens is not None:
            request["max_tokens"] = self.max_tokens
        if "claude-opus-4.7" in self.model:
            request.pop("temperature", None)
        response = self.client.chat.completions.create(
            **request,
        )
        self._record_usage(response, model=self.model)
        return response.choices[0].message.content

    def generate_structured(
        self,
        prompt: str,
        schema_name: str,
        system_message: Optional[str] = None,
        temperature: Optional[float] = None,
        model_name: Optional[str] = None,
        max_attempts: int = 3
    ) -> BaseModel:
        llm_model_name = model_name or self.model
        messages = []

        if system_message:
            messages.append({
                "role": "system",
                "content": system_message
            })

        messages.append({
            "role": "user",
            "content": prompt
        })

        response_format = LLMSchemas.get_response_format(schema_name)

        # Structured responses are sometimes cut off mid-JSON (observed
        # finish_reason="error" with a truncated object, especially when the
        # schema asks the model to embed source code inside a JSON string).
        # That is a transient failure, so retry instead of losing the step:
        # an unparsed intervention silently becomes CRS=0 and corrupts attribution.
        last_error: Optional[Exception] = None
        for attempt in range(max_attempts):
            attempt_record: Optional[Dict[str, Any]] = None
            try:
                request: Dict[str, Any] = {
                    "model": llm_model_name,
                    "messages": messages,
                    "temperature": temperature or self.temperature,
                    "response_format": response_format,
                }
                if self.max_tokens is not None:
                    request["max_tokens"] = self.max_tokens
                if "claude-opus-4.7" in llm_model_name:
                    request.pop("temperature", None)
                response = self.client.chat.completions.create(**request)
                self._record_usage(
                    response,
                    model=llm_model_name,
                    schema_name=schema_name,
                )

                content = response.choices[0].message.content
                finish_reason = getattr(response.choices[0], "finish_reason", None)
                attempt_record = {
                    "schema_name": schema_name,
                    "model": llm_model_name,
                    "attempt": attempt + 1,
                    "finish_reason": finish_reason,
                    "content_sha256": hashlib.sha256(
                        (content or "").encode("utf-8")
                    ).hexdigest(),
                    "content": content,
                    "parse_success": False,
                    "parse_error": None,
                }
                self.structured_attempts.append(attempt_record)
                if not content:
                    raise ValueError("Empty response from LLM")

                parsed_objects = convert_text_to_jsonl(content)

                if not parsed_objects:
                    raise ValueError("No valid JSON objects found in response")
                data = parsed_objects[0]

                if not isinstance(data, dict):
                    raise ValueError(f"Expected JSON object, got {type(data)}")

                if "mode" in data and "text" in data and data.get("mode") == "text":
                    try:
                        data = json.loads(content.strip())
                    except json.JSONDecodeError:
                        raise ValueError("Response is plain text, not valid JSON")

                parsed = LLMSchemas.parse_response(schema_name, data)
                attempt_record["parse_success"] = True
                return parsed

            except Exception as e:
                last_error = e
                if attempt_record is not None:
                    attempt_record["parse_error"] = f"{type(e).__name__}: {e}"
                if attempt < max_attempts - 1:
                    print(
                        f"Structured output parse failed for schema "
                        f"'{schema_name}' (attempt {attempt + 1}/{max_attempts}): {e}. Retrying."
                    )

        raise ValueError(f"Failed to parse JSON response: {last_error}")

class MultiAgentLLM:

    def __init__(
        self,
        num_agents: int = 3,
        models: Optional[List[str]] = None,
        api_key: Optional[str] = None
    ):
        self.num_agents = num_agents

        if models is None:
            default_model = os.getenv(
                "CAUSALFLOW_MODEL", "anthropic/claude-opus-4.7"
            )
            models = [default_model] * num_agents
        elif len(models) < num_agents:
            models = models + [models[0]] * (num_agents - len(models))

        self.agents = [
            LLMClient(api_key=api_key, model=model)
            for model in models[:num_agents]
        ]

    def get_agent(self, index: int) -> LLMClient:
        if 0 <= index < self.num_agents:
            return self.agents[index]
        raise IndexError(f"Agent index {index} out of range (0-{self.num_agents-1})")

    def generate_all(
        self,
        prompt: str,
        system_message: Optional[str] = None
    ) -> List[str]:
        return [
            agent.generate(prompt, system_message)
            for agent in self.agents
        ]
