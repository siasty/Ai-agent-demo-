"""
Frappe API endpoints.

Główny przepływ run_agent():
    1. Wykryj PII w zapytaniu
    2. Zakoduj PII → tokeny (ReversibleAnonymizer.encode)
    3. Wyślij ZAKODOWANE zapytanie do LLM
    4. Odbierz ZAKODOWNĄ odpowiedź z LLM
    5. Odkoduj tokeny → oryginalne dane (ReversibleAnonymizer.decode)
    6. Zwróć odkodowaną odpowiedź użytkownikowi

LLM nigdy nie widzi oryginalnych danych osobowych.
"""
from __future__ import annotations

import json

import frappe
from frappe import _

from .core.agent import Agent
from .core.anonymizer import DataAnonymizer, ReversibleAnonymizer
from .core.local_model import LocalModel
from .core.tools import get_default_tools


def _make_agent() -> Agent:
    agent = Agent(model_name="llama3.2")
    for tool in get_default_tools():
        agent.register_tool(tool)
    return agent


# ---------------------------------------------------------------------------
# GŁÓWNY ENDPOINT – pipeline z kodowaniem i odkodowaniem
# ---------------------------------------------------------------------------

@frappe.whitelist()
def run_agent(query: str, session_name: str | None = None) -> dict:
    """
    Uruchamia agenta z automatyczną anonimizacją wejścia/wyjścia.

    Przepływ:
        query (oryginalny)
            ↓ encode()
        encoded_query (tokeny zamiast PII)
            ↓ LLM
        encoded_answer
            ↓ decode()
        decoded_answer (oryginalne dane przywrócone)
    """
    if not query:
        frappe.throw(_("Zapytanie nie może być puste."))

    logs: list[dict] = []
    def emit(type_: str, label: str, data=None):
        logs.append({"type": type_, "label": label, "data": data})

    anon = ReversibleAnonymizer()

    # ------------------------------------------------------------------
    # KROK 1: Wejście oryginalne
    # ------------------------------------------------------------------
    emit("input", "Odebrano oryginalne zapytanie użytkownika", query)

    # ------------------------------------------------------------------
    # KROK 2: Wykrycie PII
    # ------------------------------------------------------------------
    findings = anon.preview(query)
    if findings:
        emit("detect", "Wykryto dane osobowe — wymagane kodowanie przed LLM", findings)
    else:
        emit("detect", "Brak danych osobowych w zapytaniu", {})

    # ------------------------------------------------------------------
    # KROK 3: Kodowanie PII → tokeny
    # ------------------------------------------------------------------
    encoded_query, token_map = anon.encode(query)

    if token_map:
        emit("encode",
             "Kodowanie: PII zastąpione tokenami [TYPE_N] — LLM zobaczy tylko tokeny",
             encoded_query)
        emit("token_map",
             "Mapa tokenów przechowywana LOKALNIE (nie trafia do LLM)",
             token_map)
    else:
        emit("encode", "Brak PII — zapytanie wysyłane bez zmian", encoded_query)

    # ------------------------------------------------------------------
    # KROK 4: Agent działa na ZAKODOWANYM tekście
    # ------------------------------------------------------------------
    tools = get_default_tools()
    emit("agent_init",
         f"Agent zainicjalizowany z {len(tools)} narzędziami",
         [t.name for t in tools])

    emit("model_req",
         "→ LocalModel.chat() — wysyłam ZAKODOWANE zapytanie do llama3.2",
         f"LLM widzi: \"{encoded_query}\"")

    agent  = _make_agent()
    result = agent.run(encoded_query)  # ← LLM operuje na tokenach!

    # ------------------------------------------------------------------
    # KROK 5: Logi per-krok agenta
    # ------------------------------------------------------------------
    for i, step in enumerate(result.get("steps", [])):
        sn        = i + 1
        tool_name = step.get("tool_name")
        thought   = step.get("thought", "")
        obs       = step.get("observation", "")

        emit("think",
             f"Krok {sn} — Myśl modelu (model widzi tokeny, nie oryginalne dane)",
             thought)

        if tool_name:
            emit("tool_select", f"Krok {sn} — Wybrane narzędzie", tool_name)
            emit("tool_input",  f"Krok {sn} — Parametry narzędzia", step.get("tool_input", {}))
            emit("tool_output", f"Krok {sn} — Wynik narzędzia (Observe)", obs)
            if i + 1 < len(result.get("steps", [])):
                emit("model_req",
                     f"→ LocalModel.chat() — obserwacja kroku {sn} → decyzja co dalej",
                     "Historia + wynik narzędzia → model")

    # ------------------------------------------------------------------
    # KROK 6: Odpowiedź z LLM (zakodowana)
    # ------------------------------------------------------------------
    encoded_answer = result.get("answer", "")
    emit("model_out",
         "← Odpowiedź LLM (może zawierać tokeny [TYPE_N])",
         encoded_answer)

    # ------------------------------------------------------------------
    # KROK 7: Odkodowanie – tokeny → oryginalne dane
    # ------------------------------------------------------------------
    decoded_answer = anon.decode(encoded_answer, token_map)

    used_tokens = {t: v for t, v in token_map.items() if t in encoded_answer}
    if used_tokens:
        emit("decode",
             "Odkodowanie: zamieniam tokeny → oryginalne wartości",
             {"odpowiedź_zakodowana": encoded_answer,
              "odpowiedź_odkodowana": decoded_answer,
              "podstawione_tokeny":   used_tokens})
    else:
        emit("decode",
             "Odkodowanie: w odpowiedzi LLM nie wystąpiły tokeny",
             decoded_answer)

    # ------------------------------------------------------------------
    # KROK 8: Wynik końcowy
    # ------------------------------------------------------------------
    emit("finish",
         "✅ Wynik końcowy przekazany użytkownikowi (odkodowany)",
         decoded_answer)

    result["answer"]        = decoded_answer
    result["encoded_query"] = encoded_query
    result["token_map"]     = token_map
    result["pipeline_log"] = logs

    _save_log(query=query, result=result, session_name=session_name)
    return result


# ---------------------------------------------------------------------------
# Pozostałe endpointy
# ---------------------------------------------------------------------------

@frappe.whitelist()
def anonymize_text(text: str, data_types: str | list | None = None) -> dict:
    if not text:
        return {"original": "", "anonymized": "", "findings": {}}
    if isinstance(data_types, str):
        data_types = json.loads(data_types) if data_types else None
    a = DataAnonymizer()
    return {"original": text, "anonymized": a.anonymize(text, data_types), "findings": a.preview(text)}


@frappe.whitelist()
def get_agent_status() -> dict:
    m = LocalModel()
    ok = m.is_available()
    return {"ollama_available": ok, "models": m.list_models() if ok else [], "default_model": m.model_name}


@frappe.whitelist()
def get_available_tools() -> list:
    return _make_agent().registry.list_tools()


@frappe.whitelist()
def create_session() -> str:
    doc = frappe.get_doc({
        "doctype": "Agent Session",
        "title": f"Sesja {frappe.utils.now_datetime().strftime('%Y-%m-%d %H:%M')}",
        "status": "Active",
        "model_name": "llama3.2",
    })
    doc.insert(ignore_permissions=True)
    return doc.name


def _save_log(query, result, session_name):
    try:
        frappe.get_doc({
            "doctype": "Agent Log",
            "session": session_name,
            "query": query,
            "answer": result.get("answer", ""),
            "steps_json": json.dumps(result.get("steps", []), ensure_ascii=False),
            "steps_count": len(result.get("steps", [])),
        }).insert(ignore_permissions=True)
    except Exception:
        pass
