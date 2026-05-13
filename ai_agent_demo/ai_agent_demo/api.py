"""
Frappe API endpoints for AI Agent Demo.
"""
from __future__ import annotations

import requests
import frappe
from frappe import _

from .core.tools import get_available_tools as get_tools_list
from .core.agent import BusinessAgent


def _check_ollama_status() -> dict:
    """Check if Ollama is available and get models."""
    try:
        # Check if Ollama is running
        response = requests.get("http://localhost:11434/api/version", timeout=3)
        if response.status_code == 200:
            # Get available models
            models_response = requests.get("http://localhost:11434/api/tags", timeout=3)
            if models_response.status_code == 200:
                models_data = models_response.json()
                models = [model["name"] for model in models_data.get("models", [])]
                return {
                    "available": True,
                    "models": models,
                    "version": response.json().get("version", "unknown")
                }
        return {"available": False, "models": [], "error": "API not responding"}
    except requests.RequestException as e:
        return {"available": False, "models": [], "error": str(e)}


@frappe.whitelist()
def get_agent_status() -> dict:
    """Get current agent status."""
    ollama_status = _check_ollama_status()

    return {
        "ollama_available": ollama_status["available"],
        "models": ollama_status["models"],
        "default_model": "llama3.2" if "llama3.2:latest" in ollama_status["models"] else "none",
        "ollama_version": ollama_status.get("version", "unknown"),
        "message": "Ollama connected" if ollama_status["available"] else f"Ollama offline: {ollama_status.get('error', 'unknown error')}"
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
    doc = frappe.get_doc({
        "doctype": "Agent Session",
        "title": f"Session {frappe.utils.now_datetime().strftime('%Y-%m-%d %H:%M')}",
        "status": "Active",
        "model_name": "llama3.2",
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