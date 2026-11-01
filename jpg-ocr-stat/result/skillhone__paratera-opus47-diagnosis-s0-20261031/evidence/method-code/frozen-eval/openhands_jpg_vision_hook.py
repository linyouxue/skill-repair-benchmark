"""Paratera alias capability wiring and scalar evidence from native serialization."""
import json
from pathlib import Path


def install():
    from openhands.sdk.llm import LLM
    original_init = LLM.__init__
    original_chat = LLM.uses_responses_api
    original_dicts = LLM._to_chat_dicts

    def is_target(model):
        return "benchflow-paratera-" in str(model)

    def initialize(self, *args, **kwargs):
        if is_target(kwargs.get("model")):
            kwargs.setdefault("model_canonical_name", "anthropic/claude-opus-4-7")
            kwargs.setdefault("disable_vision", False)
        original_init(self, *args, **kwargs)

    def uses_chat(self):
        return False if is_target(self.model) else original_chat(self)

    def serialized(self, messages):
        if not is_target(self.model):
            return original_dicts(self, messages)
        if not self.vision_is_active():
            raise RuntimeError("JPG model alias does not expose native image input")
        result = original_dicts(self, messages)
        images = [block for message in result for block in
                  (message.get("content") if isinstance(message.get("content"), list) else [])
                  if block.get("type") == "image_url"]
        inline = sum(str(x.get("image_url", {}).get("url", "")).startswith("data:image/") for x in images)
        path = Path("/logs/agent/jpg-vision-audit.jsonl")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as stream:
            stream.write(json.dumps({"model": self.model,
                "canonical_capability_model": self.model_canonical_name,
                "vision_active": True, "serialized_image_blocks": len(images),
                "inline_image_blocks": inline,
                "source": "native-sdk-chat-serialization-before-request"}) + "\n")
        return result

    LLM.__init__ = initialize
    LLM.uses_responses_api = uses_chat
    LLM._to_chat_dicts = serialized
