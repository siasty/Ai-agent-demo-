"""Shared LLM configuration and HTTP client."""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

import frappe
import requests


SETTINGS_DOCTYPE = "AI Agent LLM Settings"
LOCAL_PROVIDER = "Local Ollama"
PUBLIC_PROVIDER = "Public API"
PROVIDERS = (LOCAL_PROVIDER, PUBLIC_PROVIDER)
OLLAMA_NATIVE_FORMAT = "Ollama Native"
OPENAI_COMPATIBLE_FORMAT = "OpenAI Compatible"
PUBLIC_API_FORMATS = (OLLAMA_NATIVE_FORMAT, OPENAI_COMPATIBLE_FORMAT)

DEFAULT_LOCAL_BASE_URL = "http://localhost:11434"
DEFAULT_LOCAL_MODEL = "llama3.2"
DEFAULT_PUBLIC_BASE_URL = "https://ollama.com/api"
DEFAULT_PUBLIC_API_FORMAT = OLLAMA_NATIVE_FORMAT
DEFAULT_TIMEOUT_SECONDS = 30
MIN_TIMEOUT_SECONDS = 3
MAX_TIMEOUT_SECONDS = 120
MAX_PROMPT_CHARS = 120_000
MAX_PROVIDER_ERROR_CHARS = 240


class LLMError(Exception):
    """Base error for LLM configuration and requests."""


class LLMConfigurationError(LLMError):
    """Raised when the active LLM configuration is invalid."""


class LLMRequestError(LLMError):
    """Raised when the configured LLM endpoint cannot return a response."""


@dataclass(frozen=True)
class LLMConfig:
    """Validated active provider configuration."""

    provider: str
    api_format: str
    base_url: str
    model: str
    timeout: int
    api_key: str | None = None


def _normalize_url(value: str | None, label: str, require_https: bool) -> str:
    """Validate and normalize a provider base URL."""
    normalized = str(value or "").strip().rstrip("/")
    if not normalized:
        raise LLMConfigurationError(f"{label} is required.")
    if len(normalized) > 140:
        raise LLMConfigurationError(f"{label} cannot exceed 140 characters.")

    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise LLMConfigurationError(f"{label} must be a valid HTTP(S) URL.")
    if require_https and parsed.scheme != "https":
        raise LLMConfigurationError("Public API Base URL must use HTTPS.")
    if parsed.username or parsed.password:
        raise LLMConfigurationError(f"{label} cannot contain credentials.")
    if parsed.query or parsed.fragment:
        raise LLMConfigurationError(f"{label} cannot contain a query or fragment.")
    return normalized


def _normalize_model(value: str | None, label: str) -> str:
    """Validate a configured model name."""
    model = str(value or "").strip()
    if not model:
        raise LLMConfigurationError(f"{label} is required.")
    if len(model) > 140:
        raise LLMConfigurationError(f"{label} cannot exceed 140 characters.")
    return model


def _normalize_public_url(value: str | None, api_format: str) -> str:
    """Validate a public URL against the selected API contract."""
    normalized = _normalize_url(value, "Public API Base URL", require_https=True)
    path = urlparse(normalized).path.rstrip("/")
    if api_format == OLLAMA_NATIVE_FORMAT and not path.endswith("/api"):
        raise LLMConfigurationError(
            "Ollama Native Base URL must end with /api."
        )
    return normalized


def _normalize_timeout(value: int | str | None) -> int:
    """Validate the bounded HTTP timeout."""
    try:
        timeout = int(value or DEFAULT_TIMEOUT_SECONDS)
    except (TypeError, ValueError) as exc:
        raise LLMConfigurationError("Request Timeout must be an integer.") from exc

    if timeout < MIN_TIMEOUT_SECONDS or timeout > MAX_TIMEOUT_SECONDS:
        raise LLMConfigurationError(
            f"Request Timeout must be between {MIN_TIMEOUT_SECONDS} and "
            f"{MAX_TIMEOUT_SECONDS} seconds."
        )
    return timeout


def _extract_provider_error(response) -> str:
    """Extract a bounded provider message without exposing request secrets."""
    try:
        payload = response.json()
    except ValueError:
        return ""
    if not isinstance(payload, dict):
        return ""

    error = payload.get("error")
    if isinstance(error, dict):
        error = error.get("message")
    if not isinstance(error, str):
        return ""
    return " ".join(error.split())[:MAX_PROVIDER_ERROR_CHARS]


def build_llm_config(
    provider: str | None,
    local_base_url: str | None,
    local_model: str | None,
    public_base_url: str | None,
    public_model: str | None,
    request_timeout: int | str | None,
    api_key: str | None = None,
    public_api_format: str | None = None,
) -> LLMConfig:
    """Build a validated configuration for one active provider."""
    provider_name = str(provider or LOCAL_PROVIDER).strip()
    if provider_name not in PROVIDERS:
        raise LLMConfigurationError("Unsupported LLM provider.")
    api_format = str(public_api_format or DEFAULT_PUBLIC_API_FORMAT).strip()
    if api_format not in PUBLIC_API_FORMATS:
        raise LLMConfigurationError("Unsupported Public API Format.")

    timeout = _normalize_timeout(request_timeout)
    if provider_name == LOCAL_PROVIDER:
        return LLMConfig(
            provider=provider_name,
            api_format=api_format,
            base_url=_normalize_url(local_base_url, "Local Base URL", require_https=False),
            model=_normalize_model(local_model, "Local Model"),
            timeout=timeout,
        )

    public_key = str(api_key or "").strip()
    if not public_key:
        raise LLMConfigurationError("API Key is required for Public API.")
    return LLMConfig(
        provider=provider_name,
        api_format=api_format,
        base_url=_normalize_public_url(public_base_url, api_format),
        model=_normalize_model(public_model, "Public API Model"),
        timeout=timeout,
        api_key=public_key,
    )


def default_llm_config() -> LLMConfig:
    """Return the migration-safe default local configuration."""
    return build_llm_config(
        provider=LOCAL_PROVIDER,
        local_base_url=DEFAULT_LOCAL_BASE_URL,
        local_model=DEFAULT_LOCAL_MODEL,
        public_base_url=DEFAULT_PUBLIC_BASE_URL,
        public_model=None,
        request_timeout=DEFAULT_TIMEOUT_SECONDS,
        public_api_format=DEFAULT_PUBLIC_API_FORMAT,
    )


def load_llm_config() -> LLMConfig:
    """Load and validate the active provider from the Single DocType."""
    if not frappe.db.exists("DocType", SETTINGS_DOCTYPE):
        return default_llm_config()

    settings = frappe.get_single(SETTINGS_DOCTYPE)
    api_key = settings.get_password("api_key", raise_exception=False)
    return build_llm_config(
        provider=settings.provider_type,
        local_base_url=settings.local_base_url,
        local_model=settings.local_model,
        public_base_url=settings.public_base_url,
        public_model=settings.public_model,
        request_timeout=settings.request_timeout,
        api_key=api_key,
        public_api_format=settings.public_api_format,
    )


class LLMClient:
    """Generate text using local Ollama or a supported public API format."""

    def __init__(self, config: LLMConfig | None = None):
        self.config = config or load_llm_config()

    def generate(self, prompt: str) -> str:
        """Send one bounded prompt to the configured provider."""
        if not isinstance(prompt, str) or not prompt.strip():
            raise LLMRequestError("LLM prompt cannot be empty.")
        if len(prompt) > MAX_PROMPT_CHARS:
            raise LLMRequestError(f"LLM prompt exceeds {MAX_PROMPT_CHARS} characters.")

        if self.config.provider == LOCAL_PROVIDER:
            return self._generate_with_ollama(prompt, use_api_key=False)
        if self.config.provider == PUBLIC_PROVIDER:
            if self.config.api_format == OLLAMA_NATIVE_FORMAT:
                return self._generate_with_ollama(prompt, use_api_key=True)
            if self.config.api_format == OPENAI_COMPATIBLE_FORMAT:
                return self._generate_with_openai_api(prompt)
        raise LLMConfigurationError("Unsupported LLM provider.")

    def _generate_with_ollama(self, prompt: str, use_api_key: bool) -> str:
        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1, "top_p": 0.9},
        }
        endpoint = (
            f"{self.config.base_url}/generate"
            if use_api_key
            else f"{self.config.base_url}/api/generate"
        )
        headers = None
        if use_api_key:
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            }
        response = self._post(endpoint, payload, headers=headers)
        content = response.get("response")
        if not isinstance(content, str) or not content.strip():
            raise LLMRequestError("Ollama returned an empty response.")
        return content

    def _generate_with_openai_api(self, prompt: str) -> str:
        payload = {
            "model": self.config.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "top_p": 0.9,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        response = self._post(
            f"{self.config.base_url}/chat/completions",
            payload,
            headers=headers,
        )
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMRequestError("Public API returned an unsupported response format.") from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMRequestError("Public API returned an empty response.")
        return content

    def _post(
        self,
        url: str,
        payload: dict,
        headers: dict[str, str] | None = None,
    ) -> dict:
        """POST JSON and return a validated object without exposing secrets."""
        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=self.config.timeout,
            )
        except requests.RequestException as exc:
            raise LLMRequestError("Could not connect to the configured LLM endpoint.") from exc

        if response.status_code < 200 or response.status_code >= 300:
            detail = _extract_provider_error(response)
            suffix = f": {detail}" if detail else "."
            raise LLMRequestError(
                f"LLM API returned HTTP {response.status_code}{suffix}"
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise LLMRequestError("LLM API returned invalid JSON.") from exc
        if not isinstance(data, dict):
            raise LLMRequestError("LLM API returned an unsupported response format.")
        return data
