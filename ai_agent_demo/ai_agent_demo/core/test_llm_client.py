"""Unit tests for provider-specific LLM requests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from frappe.tests.utils import FrappeTestCase

from .llm_client import (
    LOCAL_PROVIDER,
    OLLAMA_NATIVE_FORMAT,
    OPENAI_COMPATIBLE_FORMAT,
    PUBLIC_PROVIDER,
    LLMClient,
    LLMConfigurationError,
    LLMRequestError,
    build_llm_config,
)


class TestLLMClient(FrappeTestCase):
    """Verify the HTTP contract for both supported providers."""

    @patch("ai_agent_demo.ai_agent_demo.core.llm_client.requests.post")
    def test_ollama_request_uses_local_contract(self, mock_post: MagicMock) -> None:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "response": "local answer",
            "prompt_eval_count": 11,
            "eval_count": 18,
        }
        config = build_llm_config(
            provider=LOCAL_PROVIDER,
            local_base_url="http://localhost:11434/",
            local_model="llama3.2",
            public_base_url=None,
            public_model=None,
            request_timeout=17,
        )

        result = LLMClient(config).generate("test prompt")

        self.assertEqual(result, "local answer")
        mock_post.assert_called_once_with(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.2",
                "prompt": "test prompt",
                "stream": False,
                "options": {"temperature": 0.1, "top_p": 0.9},
            },
            headers=None,
            timeout=17,
        )

    @patch("ai_agent_demo.ai_agent_demo.core.llm_client.requests.post")
    def test_public_request_uses_bearer_key_and_chat_completions(
        self,
        mock_post: MagicMock,
    ) -> None:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"content": "public answer"}}],
            "usage": {"prompt_tokens": 9, "completion_tokens": 4, "total_tokens": 13},
        }
        config = build_llm_config(
            provider=PUBLIC_PROVIDER,
            local_base_url=None,
            local_model=None,
            public_base_url="https://api.example.com/v1/",
            public_model="example-model",
            request_timeout=25,
            api_key="secret-key",
            public_api_format=OPENAI_COMPATIBLE_FORMAT,
        )

        result = LLMClient(config).generate("test prompt")

        self.assertEqual(result, "public answer")
        request = mock_post.call_args
        self.assertEqual(request.args[0], "https://api.example.com/v1/chat/completions")
        self.assertEqual(request.kwargs["headers"]["Authorization"], "Bearer secret-key")
        self.assertEqual(request.kwargs["json"]["model"], "example-model")
        self.assertEqual(
            request.kwargs["json"]["messages"],
            [{"role": "user", "content": "test prompt"}],
        )

    @patch("ai_agent_demo.ai_agent_demo.core.llm_client.requests.post")
    def test_public_ollama_uses_native_generate_contract(
        self,
        mock_post: MagicMock,
    ) -> None:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "response": "cloud answer",
            "prompt_eval_count": 7,
            "eval_count": 3,
        }
        config = build_llm_config(
            provider=PUBLIC_PROVIDER,
            local_base_url=None,
            local_model=None,
            public_base_url="https://ollama.com/api/",
            public_model="gpt-oss:120b",
            request_timeout=30,
            api_key="ollama-secret",
            public_api_format=OLLAMA_NATIVE_FORMAT,
        )

        result = LLMClient(config).generate("test prompt")

        self.assertEqual(result, "cloud answer")
        request = mock_post.call_args
        self.assertEqual(request.args[0], "https://ollama.com/api/generate")
        self.assertEqual(request.kwargs["headers"]["Authorization"], "Bearer ollama-secret")
        self.assertEqual(request.kwargs["json"]["prompt"], "test prompt")
        self.assertNotIn("messages", request.kwargs["json"])

    def test_public_api_requires_https(self) -> None:
        with self.assertRaisesRegex(LLMConfigurationError, "must use HTTPS"):
            build_llm_config(
                provider=PUBLIC_PROVIDER,
                local_base_url=None,
                local_model=None,
                public_base_url="http://api.example.com/v1",
                public_model="example-model",
                request_timeout=30,
                api_key="secret-key",
            )

    def test_public_api_requires_key(self) -> None:
        with self.assertRaisesRegex(LLMConfigurationError, "API Key is required"):
            build_llm_config(
                provider=PUBLIC_PROVIDER,
                local_base_url=None,
                local_model=None,
                public_base_url="https://api.example.com/v1",
                public_model="example-model",
                request_timeout=30,
                api_key="",
            )

    def test_native_ollama_base_url_must_end_with_api(self) -> None:
        with self.assertRaisesRegex(LLMConfigurationError, "must end with /api"):
            build_llm_config(
                provider=PUBLIC_PROVIDER,
                local_base_url=None,
                local_model=None,
                public_base_url="https://ollama.com",
                public_model="gpt-oss:120b",
                request_timeout=30,
                api_key="secret-key",
                public_api_format=OLLAMA_NATIVE_FORMAT,
            )

    def test_timeout_is_bounded(self) -> None:
        with self.assertRaisesRegex(LLMConfigurationError, "between 3 and 120"):
            build_llm_config(
                provider=LOCAL_PROVIDER,
                local_base_url="http://localhost:11434",
                local_model="llama3.2",
                public_base_url=None,
                public_model=None,
                request_timeout=121,
            )

    @patch("ai_agent_demo.ai_agent_demo.core.llm_client.requests.post")
    def test_provider_error_message_is_returned_without_request_data(
        self,
        mock_post: MagicMock,
    ) -> None:
        mock_post.return_value.status_code = 404
        mock_post.return_value.json.return_value = {
            "error": "model 'local-only:latest' not found"
        }
        config = build_llm_config(
            provider=PUBLIC_PROVIDER,
            local_base_url=None,
            local_model=None,
            public_base_url="https://ollama.com/api",
            public_model="local-only:latest",
            request_timeout=30,
            api_key="secret-key",
            public_api_format=OLLAMA_NATIVE_FORMAT,
        )

        with self.assertRaisesRegex(
            LLMRequestError,
            "HTTP 404: model 'local-only:latest' not found",
        ):
            LLMClient(config).generate("test prompt")
