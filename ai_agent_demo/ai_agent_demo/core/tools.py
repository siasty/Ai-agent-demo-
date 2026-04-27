"""
Narzędzia agenta – wzorzec OOP.

Każde narzędzie dziedziczy po abstrakcyjnej klasie Tool
i implementuje metodę execute(). Nowe narzędzie = nowa klasa.

Hierarchia:
    Tool (ABC)
    ├── AnonymizationTool
    ├── DatabaseSearchTool
    ├── DataAnalysisTool
    └── DateTimeTool

ToolRegistry zarządza rejestrem narzędzi.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import frappe


# ===========================================================================
# Interfejs bazowy
# ===========================================================================

class Tool(ABC):
    """
    Abstrakcyjna klasa bazowa dla wszystkich narzędzi agenta.

    Każde narzędzie musi zdefiniować:
        name        – unikalny identyfikator (snake_case)
        description – opis dla LLM (po polsku, zwięzły)
        parameters  – słownik {nazwa: typ_i_opis}
    """

    name: str = ""
    description: str = ""
    parameters: dict[str, str] = {}

    @abstractmethod
    def execute(self, params: dict) -> Any:
        """Wykonuje narzędzie z podanymi parametrami."""
        ...

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


# ===========================================================================
# Rejestr narzędzi
# ===========================================================================

class ToolRegistry:
    """
    Przechowuje dostępne narzędzia i udostępnia je agentowi.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[dict]:
        return [t.to_dict() for t in self._tools.values()]

    def descriptions_for_prompt(self) -> str:
        """Zwraca opis narzędzi gotowy do wklejenia w system prompt."""
        lines = []
        for tool in self._tools.values():
            params = ", ".join(
                f"{k}: {v}" for k, v in tool.parameters.items()
            )
            lines.append(f"- {tool.name}({params}): {tool.description}")
        return "\n".join(lines)


# ===========================================================================
# Implementacje narzędzi
# ===========================================================================

class AnonymizationTool(Tool):
    """
    Anonimizuje wrażliwe dane osobowe w tekście.
    Deleguje pracę do klasy DataAnonymizer.
    """

    name = "anonymize_data"
    description = "Anonimizuje wrażliwe dane osobowe w tekście (email, telefon, PESEL, imiona)"
    parameters = {
        "text": "str – tekst do anonimizacji",
        "data_types": "list[str] – typy: email, phone, pesel, name (domyślnie wszystkie)",
    }

    def execute(self, params: dict) -> str:
        from .anonymizer import DataAnonymizer
        anonymizer = DataAnonymizer()
        text = params.get("text", "")
        data_types = params.get("data_types") or None
        return anonymizer.anonymize(text, data_types)


class DatabaseSearchTool(Tool):
    """
    Przeszukuje wybrany DocType Frappe po nazwie.
    """

    name = "search_database"
    description = "Wyszukuje rekordy w bazie danych Frappe po frazie"
    parameters = {
        "doctype": "str – nazwa DocType (np. Customer, Item)",
        "query": "str – szukana fraza",
    }

    def execute(self, params: dict) -> str:
        doctype = params.get("doctype", "")
        query = params.get("query", "")

        if not doctype:
            return "Błąd: podaj nazwę DocType."
        if not frappe.db.exists("DocType", doctype):
            return f"DocType '{doctype}' nie istnieje w tym systemie."

        try:
            results = frappe.get_list(
                doctype,
                filters=[["name", "like", f"%{query}%"]],
                fields=["name"],
                limit=5,
                ignore_permissions=True,
            )
            if not results:
                return f"Brak wyników dla '{query}' w {doctype}."
            names = [r.name for r in results]
            return f"Znaleziono {len(names)} rekordów: {', '.join(names)}"
        except Exception as exc:
            return f"Błąd wyszukiwania: {exc}"


class DataAnalysisTool(Tool):
    """
    Oblicza podstawowe statystyki listy liczb.
    """

    name = "analyze_data"
    description = "Oblicza statystyki listy liczb: suma, średnia, min, max"
    parameters = {
        "numbers": "list[float] – lista liczb do analizy",
    }

    def execute(self, params: dict) -> str:
        raw = params.get("numbers", [])
        if not raw:
            return "Brak danych – podaj listę liczb."
        try:
            nums = [float(n) for n in raw]
        except (ValueError, TypeError) as exc:
            return f"Błąd konwersji: {exc}"

        return (
            f"Analiza {len(nums)} wartości: "
            f"suma={sum(nums):.2f}, "
            f"średnia={sum(nums)/len(nums):.2f}, "
            f"min={min(nums):.2f}, "
            f"max={max(nums):.2f}"
        )


class DateTimeTool(Tool):
    """
    Zwraca aktualną datę i godzinę serwera.
    """

    name = "get_datetime"
    description = "Zwraca aktualną datę i godzinę"
    parameters = {}

    def execute(self, params: dict) -> str:
        from datetime import datetime
        now = datetime.now()
        return f"Aktualna data i godzina: {now.strftime('%Y-%m-%d %H:%M:%S')}"


# ===========================================================================
# Fabryka domyślnego zestawu narzędzi
# ===========================================================================

def get_default_tools() -> list[Tool]:
    """Zwraca domyślny zestaw narzędzi dla demo agenta."""
    from .erp_tools import get_erp_tools

    base_tools = [
        AnonymizationTool(),
        DatabaseSearchTool(),
        DataAnalysisTool(),
        DateTimeTool(),
    ]

    # Dodaj narzędzia ERPNext
    erp_tools = get_erp_tools()

    return base_tools + erp_tools
