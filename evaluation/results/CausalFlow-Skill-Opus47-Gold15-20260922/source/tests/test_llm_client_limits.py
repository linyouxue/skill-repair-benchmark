import unittest
import hashlib
from types import SimpleNamespace
from unittest.mock import patch

from llm_client import LLMClient


class LLMClientLimitTests(unittest.TestCase):
    def test_configured_max_tokens_is_forwarded(self):
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
            usage=None,
        )
        with patch("llm_client.OpenAI") as openai:
            openai.return_value.chat.completions.create.return_value = response
            client = LLMClient(api_key="test", model="test/model", max_tokens=32_768)
            self.assertEqual(client.generate("prompt"), "ok")

        kwargs = openai.return_value.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["max_tokens"], 32_768)

    def test_nonpositive_max_tokens_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "max_tokens must be positive"):
            LLMClient(api_key="test", max_tokens=0)

    def test_structured_response_content_and_hash_are_recorded(self):
        content = '{"explanation":"fixed"}'
        response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=content),
                    finish_reason="stop",
                )
            ],
            usage=None,
        )
        with patch("llm_client.OpenAI") as openai:
            openai.return_value.chat.completions.create.return_value = response
            client = LLMClient(api_key="test", model="test/model")
            parsed = client.generate_structured(
                "prompt", "intervention", max_attempts=1
            )

        self.assertEqual(parsed.explanation, "fixed")
        record = client.structured_attempts[0]
        self.assertTrue(record["parse_success"])
        self.assertEqual(record["finish_reason"], "stop")
        self.assertEqual(record["content"], content)
        self.assertEqual(
            record["content_sha256"], hashlib.sha256(content.encode()).hexdigest()
        )

    def test_structured_parse_failure_is_preserved(self):
        response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="not json"),
                    finish_reason="stop",
                )
            ],
            usage=None,
        )
        with patch("llm_client.OpenAI") as openai:
            openai.return_value.chat.completions.create.return_value = response
            client = LLMClient(api_key="test", model="test/model")
            with self.assertRaises(ValueError):
                client.generate_structured(
                    "prompt", "intervention", max_attempts=1
                )

        record = client.structured_attempts[0]
        self.assertFalse(record["parse_success"])
        self.assertIn("plain text", record["parse_error"])


if __name__ == "__main__":
    unittest.main()
