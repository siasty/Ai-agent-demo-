"""
Frappe API endpoints.

Whitelisted metody wywoływane z frontendu (Frappe Page).
Każda metoda jest cienką warstwą – właściwa logika jest w core/.
"""
from __future__ import annotations

import json

import frappe
from frappe import _

from .core.agent import Agent
from .core.anonymizer import DataAnonymizer
from .core.local_model import LocalModel
from .core.tools import get_default_tools


# ---------------------------------------------------------------------------
# Pomocnicza fabryka agenta
# ---------------------------------------------------------------------------

def _make_agent() -> Agent:
    """Buduje agenta z domyślnym zestawem narzędzi."""
    agent = Agent(model_name="llama3.2")
    for tool in get_default_tools():
        agent.register_tool(tool)
    return agent


# ---------------------------------------------------------------------------
# Endpointy
# ---------------------------------------------------------------------------

@frappe.whitelist()
def run_agent(query: str, session_name: str | None = None) -> dict:
    """Uruchamia agenta na zapytaniu użytkownika."""
    if not query:
        frappe.throw(_("Zapytanie nie może być puste."))

    agent = _make_agent()
    result = agent.run(query)

    _save_log(query=query, result=result, session_name=session_name)
    return result


@frappe.whitelist()
def anonymize_text(text: str, data_types: str | list | None = None) -> dict:
    """Anonimizuje dane osobowe w tekście."""
    if not text:
        return {"original": "", "anonymized": "", "findings": {}}

    if isinstance(data_types, str):
        data_types = json.loads(data_types) if data_types else None

    anonymizer = DataAnonymizer()
    findings = anonymizer.preview(text)
    anonymized = anonymizer.anonymize(text, data_types)

    return {"original": text, "anonymized": anonymized, "findings": findings}


@frappe.whitelist()
def get_agent_status() -> dict:
    """Sprawdza czy Ollama jest dostępna i zwraca listę modeli."""
    model = LocalModel()
    available = model.is_available()
    return {
        "ollama_available": available,
        "models": model.list_models() if available else [],
        "default_model": model.model_name,
    }


@frappe.whitelist()
def get_available_tools() -> list:
    """Zwraca listę narzędzi z opisami (do wyświetlenia w UI)."""
    agent = _make_agent()
    return agent.registry.list_tools()


@frappe.whitelist()
def create_session() -> str:
    """Tworzy nową sesję agenta i zwraca jej nazwę."""
    doc = frappe.get_doc({
        "doctype": "Agent Session",
        "title": f"Sesja {frappe.utils.now_datetime().strftime('%Y-%m-%d %H:%M')}",
        "status": "Active",
        "model_name": "llama3.2",
    })
    doc.insert(ignore_permissions=True)
    return doc.name


# ---------------------------------------------------------------------------
# Wewnętrzna – zapis logu
# ---------------------------------------------------------------------------

def _save_log(query: str, result: dict, session_name: str | None) -> None:
    try:
        doc = frappe.get_doc({
            "doctype": "Agent Log",
            "session": session_name,
            "query": query,
            "answer": result.get("answer", ""),
            "steps_json": json.dumps(result.get("steps", []), ensure_ascii=False),
            "steps_count": len(result.get("steps", [])),
        })
        doc.insert(ignore_permissions=True)
    except Exception:
        pass  # logowanie nie może blokować odpowiedzi dla użytkownika
