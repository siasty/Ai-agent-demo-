"""
Frappe API endpoints.

Każda whitelisted metoda jest cienką warstwą – logika w core/.
run_agent() buduje szczegółowy pipeline_log z każdego kroku wykonania.
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
    agent = Agent(model_name="llama3.2")
    for tool in get_default_tools():
        agent.register_tool(tool)
    return agent


# ---------------------------------------------------------------------------
# Endpointy
# ---------------------------------------------------------------------------

@frappe.whitelist()
def run_agent(query: str, session_name: str | None = None) -> dict:
    """
    Uruchamia agenta i zwraca:
        answer       – finalna odpowiedź
        steps        – surowe kroki ReAct
        pipeline_log – szczegółowy log każdego zdarzenia (do wizualizacji)
    """
    if not query:
        frappe.throw(_("Zapytanie nie może być puste."))

    logs: list[dict] = []

    def emit(type_: str, label: str, data=None) -> None:
        logs.append({"type": type_, "label": label, "data": data})

    anonymizer = DataAnonymizer()

    # ------------------------------------------------------------------
    # 1. Wejście użytkownika
    # ------------------------------------------------------------------
    emit("input", "Odebrano zapytanie od użytkownika", query)

    # ------------------------------------------------------------------
    # 2. Pre-processing – skanowanie zapytania pod kątem danych osobowych
    # ------------------------------------------------------------------
    emit("preprocess", "Pre-processing: skanuję zapytanie pod kątem danych osobowych", None)

    query_findings = anonymizer.preview(query)
    if query_findings:
        emit("detect", "Wykryto dane osobowe w zapytaniu — wymagana anonimizacja", query_findings)
    else:
        emit("detect", "Brak danych osobowych w zapytaniu", {})

    # ------------------------------------------------------------------
    # 3. Inicjalizacja agenta
    # ------------------------------------------------------------------
    tools = get_default_tools()
    emit(
        "agent_init",
        f"Agent zainicjalizowany z {len(tools)} narzędziami",
        [t.name for t in tools],
    )

    # ------------------------------------------------------------------
    # 4. Pierwsze wywołanie modelu
    # ------------------------------------------------------------------
    emit(
        "model_req",
        "→ LocalModel.chat() — wysyłam system prompt + zapytanie do llama3.2",
        "System prompt zawiera listę narzędzi i instrukcję formatu JSON",
    )

    # ------------------------------------------------------------------
    # 5. Uruchomienie agenta (pętla ReAct)
    # ------------------------------------------------------------------
    agent = _make_agent()
    result = agent.run(query)

    # ------------------------------------------------------------------
    # 6. Log per-krok
    # ------------------------------------------------------------------
    steps = result.get("steps", [])

    for i, step in enumerate(steps):
        step_num  = i + 1
        tool_name = step.get("tool_name")
        tool_input = step.get("tool_input", {})
        thought    = step.get("thought", "")
        observation = step.get("observation", "")

        # Myśl modelu
        emit("think", f"Krok {step_num} — Myśl modelu (Reason)", thought)

        if tool_name:
            # Wybór narzędzia
            emit("tool_select", f"Krok {step_num} — Wybrane narzędzie (Act)", tool_name)

            # Parametry wejściowe
            emit("tool_input", f"Krok {step_num} — Parametry przekazane do narzędzia", tool_input)

            # Szczegółowe zdarzenia anonimizacji
            if tool_name == "anonymize_data":
                text_arg  = tool_input.get("text", "")
                types_arg = tool_input.get("data_types")
                if text_arg:
                    emit(
                        "anon_start",
                        "DataAnonymizer.anonymize_verbose() — analizuję tekst",
                        f"Strategii do zastosowania: {types_arg or ['pesel','email','phone','name']}",
                    )
                    verbose = anonymizer.anonymize_verbose(text_arg, types_arg)
                    for change in verbose.get("changes", []):
                        dtype  = change["type"]
                        count  = change["count"]
                        noun   = "zmiana" if count == 1 else ("zmiany" if count < 5 else "zmian")
                        emit(
                            "anonymize_change",
                            f"Anonimizacja [{dtype}] — {count} {noun}",
                            change,
                        )
                    emit(
                        "anon_done",
                        "Anonimizacja zakończona — wynik trafia do obserwacji agenta",
                        f"Zanonimizowano: {[c['type'] for c in verbose.get('changes', [])]}",
                    )

            # Wynik narzędzia (Observe)
            emit("tool_output", f"Krok {step_num} — Wynik narzędzia (Observe)", observation)

            # Kolejne wywołanie modelu (jeśli nie ostatni krok)
            if i + 1 < len(steps):
                emit(
                    "model_req",
                    f"→ LocalModel.chat() — obserwacja kroku {step_num} → model decyduje co dalej",
                    "Historia: zapytanie + poprzednie kroki + wynik narzędzia",
                )

    # ------------------------------------------------------------------
    # 7. Finalna odpowiedź
    # ------------------------------------------------------------------
    emit("finish", "✅ Odpowiedź końcowa gotowa", result.get("answer", ""))

    result["pipeline_log"] = logs
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
    findings   = anonymizer.preview(text)
    anonymized = anonymizer.anonymize(text, data_types)

    return {"original": text, "anonymized": anonymized, "findings": findings}


@frappe.whitelist()
def get_agent_status() -> dict:
    """Sprawdza czy Ollama jest dostępna."""
    model = LocalModel()
    available = model.is_available()
    return {
        "ollama_available": available,
        "models": model.list_models() if available else [],
        "default_model": model.model_name,
    }


@frappe.whitelist()
def get_available_tools() -> list:
    """Zwraca listę narzędzi z opisami."""
    return _make_agent().registry.list_tools()


@frappe.whitelist()
def create_session() -> str:
    """Tworzy nową sesję agenta."""
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
        pass
