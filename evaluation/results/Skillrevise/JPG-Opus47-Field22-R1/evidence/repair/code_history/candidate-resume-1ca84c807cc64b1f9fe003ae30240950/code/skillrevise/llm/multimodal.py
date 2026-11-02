"""Typed multimodal transport; images are content blocks, never prompt strings."""
from __future__ import annotations

import base64
import gzip
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class MultimodalPrompt:
    messages: list[dict[str, Any]]
    evidence_root: str
    context: dict[str, Any] = field(default_factory=dict)


def write_json_gzip(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=True)


def image_source(block: dict[str, Any]) -> tuple[str, str]:
    if block.get("type") != "image_url":
        raise ValueError("Expected an image_url block")
    url = block["image_url"]["url"]
    if not isinstance(url, str) or not url.startswith("data:image/") or ";base64," not in url:
        raise ValueError("Expected actual image bytes in a base64 data URL")
    header, data = url.split(";base64,", 1)
    if not base64.b64decode(data, validate=True):
        raise ValueError("Empty image bytes")
    return header.removeprefix("data:"), data


def validate_messages(messages: list[dict[str, Any]]) -> None:
    if not messages:
        raise ValueError("Empty multimodal messages")
    for message in messages:
        if message.get("role") != "user" or not isinstance(message.get("content"), list):
            raise ValueError("Multimodal transport expects user messages with content blocks")
        for block in message["content"]:
            if block.get("type") == "image_url":
                image_source(block)
            elif block.get("type") != "text" or not isinstance(block.get("text"), str):
                raise ValueError("Unsupported multimodal content block")


def provider_messages(prompt: str | MultimodalPrompt, *, anthropic: bool = False) -> list[dict[str, Any]]:
    if isinstance(prompt, str):
        return [{"role": "user", "content": prompt}]
    validate_messages(prompt.messages)
    if not anthropic:
        return prompt.messages
    messages = []
    for message in prompt.messages:
        blocks = []
        for block in message["content"]:
            if block["type"] == "text":
                blocks.append(block)
            else:
                mime, data = image_source(block)
                blocks.append({"type": "image", "source": {"type": "base64", "media_type": mime, "data": data}})
        messages.append({"role": "user", "content": blocks})
    return messages
