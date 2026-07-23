"""Validation for AI Agent LLM Settings."""
from __future__ import annotations

from frappe.model.document import Document

from ...core.llm_client import (
    LOCAL_PROVIDER,
    PUBLIC_PROVIDER,
    build_llm_config,
)


class AIAgentLLMSettings(Document):
    """Global provider settings for the AI Agent Demo."""

    def validate(self) -> None:
        """Validate the active provider and normalize persisted values."""
        api_key = self.get_password("api_key", raise_exception=False)
        config = build_llm_config(
            provider=self.provider_type,
            local_base_url=self.local_base_url,
            local_model=self.local_model,
            public_base_url=self.public_base_url,
            public_model=self.public_model,
            request_timeout=self.request_timeout,
            api_key=api_key,
            public_api_format=self.public_api_format,
        )

        self.provider_type = config.provider
        self.request_timeout = config.timeout
        self.public_api_format = config.api_format
        if config.provider == LOCAL_PROVIDER:
            self.local_base_url = config.base_url
            self.local_model = config.model
            return

        if config.provider == PUBLIC_PROVIDER:
            self.public_base_url = config.base_url
            self.public_model = config.model
