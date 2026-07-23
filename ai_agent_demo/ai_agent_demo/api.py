"""
Frappe API endpoints for AI Agent Demo.
"""
from __future__ import annotations

from urllib.parse import urlparse

import frappe
import requests
from frappe import _
from frappe.utils import cint

from .core.agent import BusinessAgent
from .core.llm_client import (
    DEFAULT_LOCAL_BASE_URL,
    DEFAULT_LOCAL_MODEL,
    DEFAULT_PUBLIC_API_FORMAT,
    DEFAULT_PUBLIC_BASE_URL,
    DEFAULT_TIMEOUT_SECONDS,
    LOCAL_PROVIDER,
    OLLAMA_NATIVE_FORMAT,
    PUBLIC_PROVIDER,
    SETTINGS_DOCTYPE,
    LLMClient,
    LLMConfigurationError,
    LLMError,
    build_llm_config,
    load_llm_config,
)
from .core.tools import get_available_tools as get_tools_list


OLLAMA_CLOUD_HOSTS = frozenset({"ollama.com", "www.ollama.com"})
OLLAMA_USAGE_URL = "https://ollama.com/settings"


def _get_provider_usage_url(config) -> str | None:
    """Return an authoritative usage page only for a recognized provider."""
    if config.provider != PUBLIC_PROVIDER:
        return None
    if config.api_format != OLLAMA_NATIVE_FORMAT:
        return None

    hostname = urlparse(config.base_url).hostname
    if hostname not in OLLAMA_CLOUD_HOSTS:
        return None
    return OLLAMA_USAGE_URL


def _require_settings_access(permission_type: str) -> None:
    """Limit LLM configuration endpoints to System Managers."""
    frappe.only_for("System Manager")
    frappe.has_permission(
        SETTINGS_DOCTYPE,
        ptype=permission_type,
        throw=True,
    )


def _get_settings_doc():
    """Return the global settings document after migration."""
    if not frappe.db.exists("DocType", SETTINGS_DOCTYPE):
        frappe.throw(_("AI Agent LLM Settings are not installed. Run site migration."))
    return frappe.get_single(SETTINGS_DOCTYPE)


def _serialize_settings(settings) -> dict:
    """Return settings safe for the browser, excluding the API key."""
    api_key = settings.get_password("api_key", raise_exception=False)
    return {
        "provider_type": settings.provider_type or LOCAL_PROVIDER,
        "request_timeout": settings.request_timeout or DEFAULT_TIMEOUT_SECONDS,
        "local_base_url": settings.local_base_url or DEFAULT_LOCAL_BASE_URL,
        "local_model": settings.local_model or DEFAULT_LOCAL_MODEL,
        "public_base_url": settings.public_base_url or DEFAULT_PUBLIC_BASE_URL,
        "public_api_format": settings.public_api_format or DEFAULT_PUBLIC_API_FORMAT,
        "public_model": settings.public_model or "",
        "api_key_set": bool(api_key),
    }


def _effective_api_key(settings, api_key: str | None, clear_api_key: int | str) -> str | None:
    """Resolve a submitted key without returning the stored key to the client."""
    if cint(clear_api_key):
        return None
    submitted_key = str(api_key or "").strip()
    if submitted_key:
        return submitted_key
    return settings.get_password("api_key", raise_exception=False)


def _build_submitted_config(
    settings,
    provider_type: str,
    request_timeout: int | str,
    local_base_url: str,
    local_model: str,
    public_base_url: str,
    public_model: str,
    public_api_format: str,
    api_key: str | None,
    clear_api_key: int | str,
):
    """Build a validated config from dialog values and the stored secret."""
    effective_key = _effective_api_key(settings, api_key, clear_api_key)
    return build_llm_config(
        provider=provider_type,
        local_base_url=local_base_url,
        local_model=local_model,
        public_base_url=public_base_url,
        public_model=public_model,
        request_timeout=request_timeout,
        api_key=effective_key,
        public_api_format=public_api_format,
    )


def _check_ollama_status(base_url: str, timeout: int) -> dict:
    """Check the configured Ollama endpoint and list at most 50 models."""
    if not base_url:
        return {"available": False, "models": [], "error": "Base URL is missing"}

    try:
        status_timeout = min(max(timeout, 3), 5)
        version_response = requests.get(f"{base_url}/api/version", timeout=status_timeout)
        if version_response.status_code != 200:
            return {
                "available": False,
                "models": [],
                "error": f"HTTP {version_response.status_code}",
            }

        models_response = requests.get(f"{base_url}/api/tags", timeout=status_timeout)
        models = []
        if models_response.status_code == 200:
            models_data = models_response.json()
            models = [
                model.get("name")
                for model in models_data.get("models", [])[:50]
                if isinstance(model, dict) and model.get("name")
            ]
        return {
            "available": True,
            "models": models,
            "version": version_response.json().get("version", "unknown"),
        }
    except (requests.RequestException, ValueError, TypeError, AttributeError):
        return {"available": False, "models": [], "error": "API not responding"}


@frappe.whitelist()
def get_agent_status() -> dict:
    """Return a provider-aware status without making a billable public request."""
    can_configure = "System Manager" in frappe.get_roles()
    try:
        config = load_llm_config()
    except LLMConfigurationError as exc:
        return {
            "available": False,
            "ollama_available": False,
            "provider": "Not configured",
            "model": "",
            "models": [],
            "message": str(exc),
            "can_configure": can_configure,
        }

    if config.provider == PUBLIC_PROVIDER:
        return {
            "available": True,
            "connection_verified": False,
            "ollama_available": False,
            "provider": config.provider,
            "api_format": config.api_format,
            "provider_label": f"{config.provider} ({config.api_format})",
            "model": config.model,
            "models": [config.model],
            "message": "Public API configured; use Test connection to verify it.",
            "usage_url": _get_provider_usage_url(config),
            "can_configure": can_configure,
        }

    ollama_status = _check_ollama_status(config.base_url, config.timeout)
    available = ollama_status["available"]
    return {
        "available": available,
        "connection_verified": available,
        "ollama_available": available,
        "provider": LOCAL_PROVIDER,
        "model": config.model,
        "models": ollama_status["models"],
        "ollama_version": ollama_status.get("version", "unknown"),
        "message": (
            "Local Ollama connected"
            if available
            else f"Local Ollama offline: {ollama_status.get('error', 'unknown error')}"
        ),
        "can_configure": can_configure,
    }


@frappe.whitelist()
def get_llm_settings() -> dict:
    """Return global LLM settings without exposing the encrypted API key."""
    _require_settings_access("read")
    return _serialize_settings(_get_settings_doc())


@frappe.whitelist(methods=["POST"])
def save_llm_settings(
    provider_type: str,
    request_timeout: int | str,
    local_base_url: str,
    local_model: str,
    public_base_url: str,
    public_model: str,
    public_api_format: str = DEFAULT_PUBLIC_API_FORMAT,
    api_key: str | None = None,
    clear_api_key: int | str = 0,
) -> dict:
    """Validate and save the active LLM provider."""
    _require_settings_access("write")
    settings = _get_settings_doc()
    config = _build_submitted_config(
        settings=settings,
        provider_type=provider_type,
        request_timeout=request_timeout,
        local_base_url=local_base_url,
        local_model=local_model,
        public_base_url=public_base_url,
        public_model=public_model,
        public_api_format=public_api_format,
        api_key=api_key,
        clear_api_key=clear_api_key,
    )

    settings.provider_type = provider_type
    settings.request_timeout = config.timeout
    settings.local_base_url = local_base_url
    settings.local_model = local_model
    settings.public_base_url = public_base_url
    settings.public_model = public_model
    settings.public_api_format = config.api_format
    if cint(clear_api_key):
        settings.api_key = ""
    elif str(api_key or "").strip():
        settings.api_key = str(api_key).strip()
    settings.save()
    return _serialize_settings(settings)


@frappe.whitelist(methods=["POST"])
def test_llm_settings(
    provider_type: str,
    request_timeout: int | str,
    local_base_url: str,
    local_model: str,
    public_base_url: str,
    public_model: str,
    public_api_format: str = DEFAULT_PUBLIC_API_FORMAT,
    api_key: str | None = None,
    clear_api_key: int | str = 0,
) -> dict:
    """Test submitted settings with a small explicit model request."""
    _require_settings_access("write")
    settings = _get_settings_doc()
    config = _build_submitted_config(
        settings=settings,
        provider_type=provider_type,
        request_timeout=request_timeout,
        local_base_url=local_base_url,
        local_model=local_model,
        public_base_url=public_base_url,
        public_model=public_model,
        public_api_format=public_api_format,
        api_key=api_key,
        clear_api_key=clear_api_key,
    )
    client = LLMClient(config)
    try:
        response = client.generate("Reply with exactly: OK")
    except LLMError as exc:
        frappe.throw(_("Connection test failed: {0}").format(str(exc)))

    return {
        "success": True,
        "provider": config.provider,
        "api_format": config.api_format,
        "model": config.model,
        "response_preview": response.strip()[:200],
    }


@frappe.whitelist()
def get_available_tools() -> list:
    """Get list of available tools."""
    tools = get_tools_list()
    return [
        {
            "name": tool.get("name", "unknown"),
            "description": tool.get("description", "No description")
        }
        for tool in tools
    ]


@frappe.whitelist()
def run_agent(query: str, session_name: str | None = None) -> dict:
    """
    Run agent with given query.

    Args:
        query: User query
        session_name: Optional session name

    Returns:
        Result dict with answer and pipeline_log
    """
    if not query:
        frappe.throw(_("Query cannot be empty."))

    try:
        # Create business agent
        agent = BusinessAgent()

        # Execute query
        result = agent.run(query)

        # Save log if session provided
        if session_name and result.get("answer"):
            _save_log(
                query=query,
                result=result,
                session_name=session_name
            )

        return result

    except Exception as e:
        frappe.log_error(f"Agent execution failed: {str(e)}")
        return {
            "answer": f"Agent execution failed: {str(e)}",
            "pipeline_log": [
                {
                    "type": "error",
                    "message": "Agent execution failed",
                    "data": str(e)
                }
            ]
        }


@frappe.whitelist()
def create_session() -> str:
    """Create new agent session."""
    config = load_llm_config()
    doc = frappe.get_doc({
        "doctype": "Agent Session",
        "title": f"Session {frappe.utils.now_datetime().strftime('%Y-%m-%d %H:%M')}",
        "status": "Active",
        "model_name": config.model,
    })
    doc.insert(ignore_permissions=True)
    return doc.name


def _save_log(query: str, result: dict, session_name: str | None = None):
    """Save agent execution log to database."""
    try:
        import json

        frappe.get_doc({
            "doctype": "Agent Log",
            "session": session_name,
            "query": query,
            "answer": result.get("answer", ""),
            "steps_json": json.dumps(result.get("steps", []), ensure_ascii=False),
            "steps_count": len(result.get("steps", [])),
        }).insert(ignore_permissions=True)
    except Exception:
        pass  # Don't fail the main operation if logging fails
