"""
Agent AI – implementacja wzorca ReAct (Reason + Act).

Przebieg jednego kroku agenta:
    1. Myśl  – LLM analizuje zapytanie i wybiera narzędzie
    2. Działaj – wywołuje wybrane narzędzie z parametrami
    3. Obserwuj – przetwarza wynik i decyduje czy kontynuować

Klasy:
    AgentStep  – dane jednego kroku (thought / tool / observation)
    Agent      – główna pętla ReAct
"""
from __future__ import annotations

import json
import re

from .local_model import LocalModel
from .tools import Tool, ToolRegistry


# ===========================================================================
# Krok agenta
# ===========================================================================

class AgentStep:
    """
    Reprezentuje jeden krok w procesie rozumowania agenta.

    Atrybuty:
        thought:     co agent "pomyślał" przed działaniem
        tool_name:   nazwa wywołanego narzędzia (None = brak)
        tool_input:  parametry przekazane do narzędzia
        observation: wynik działania narzędzia
    """

    def __init__(
        self,
        thought: str,
        tool_name: str | None = None,
        tool_input: dict | None = None,
        observation: str | None = None,
    ) -> None:
        self.thought = thought
        self.tool_name = tool_name
        self.tool_input = tool_input or {}
        self.observation = observation

    def to_dict(self) -> dict:
        return {
            "thought": self.thought,
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "observation": self.observation,
        }


# ===========================================================================
# Agent
# ===========================================================================

class Agent:
    """
    Koordynator pętli ReAct.

    Odpowiada za:
    - utrzymanie kontekstu rozmowy
    - zarządzanie narzędziami przez ToolRegistry
    - komunikację z lokalnym LLM przez LocalModel
    - zbieranie kroków AgentStep dla wizualizacji w UI
    """

    MAX_STEPS = 5  # zabezpieczenie przed nieskończoną pętlą

    def __init__(self, model_name: str = "llama3.2") -> None:
        self.model = LocalModel(model_name)
        self.registry = ToolRegistry()
        self.steps: list[AgentStep] = []

    # ------------------------------------------------------------------
    # Rejestracja narzędzi
    # ------------------------------------------------------------------

    def register_tool(self, tool: Tool) -> None:
        self.registry.register(tool)

    # ------------------------------------------------------------------
    # Główna pętla
    # ------------------------------------------------------------------

    def run(self, query: str) -> dict:
        """
        Uruchamia agenta na podanym zapytaniu.

        Zwraca słownik:
            {
                "answer": str,        # finalna odpowiedź
                "steps":  list[dict], # lista kroków do wizualizacji
            }
        """
        self.steps = []
        messages = [{"role": "user", "content": query}]

        for _ in range(self.MAX_STEPS):
            # --- Myśl (Reason) ---
            response = self.model.chat(
                system=self._build_system_prompt(),
                messages=messages,
            )

            parsed = self._parse_json(response)
            thought = parsed.get("thought", "")
            tool_name = parsed.get("tool", "FINISH")

            # --- Zakończ ---
            if tool_name == "FINISH":
                self.steps.append(AgentStep(thought=thought))
                return {
                    "answer": parsed.get("answer", response),
                    "steps": [s.to_dict() for s in self.steps],
                }

            # --- Działaj (Act) ---
            tool_input = parsed.get("input", {})
            tool = self.registry.get(tool_name)

            if tool is None:
                observation = f"Błąd: narzędzie '{tool_name}' nie istnieje."
            else:
                observation = str(tool.execute(tool_input))

            step = AgentStep(
                thought=thought,
                tool_name=tool_name,
                tool_input=tool_input,
                observation=observation,
            )
            self.steps.append(step)

            # --- Obserwuj (Observe) – dodaj do kontekstu ---
            messages.append({"role": "assistant", "content": response})
            messages.append({
                "role": "user",
                "content": (
                    f"Wynik narzędzia `{tool_name}`: {observation}\n\n"
                    "Jeśli masz wystarczającą odpowiedź, zakończ (FINISH). "
                    "Jeśli potrzebujesz kolejnego kroku, wywołaj następne narzędzie."
                ),
            })

        # przekroczono MAX_STEPS
        return {
            "answer": "Przekroczono maksymalną liczbę kroków agenta.",
            "steps": [s.to_dict() for s in self.steps],
        }

    # ------------------------------------------------------------------
    # Pomocnicze
    # ------------------------------------------------------------------

    def _build_system_prompt(self) -> str:
        tools_desc = self.registry.descriptions_for_prompt()
        return (
            "Jesteś pomocnym asystentem AI. "
            "Aby odpowiedzieć na zapytanie możesz używać narzędzi.\n\n"
            f"Dostępne narzędzia:\n{tools_desc}\n\n"
            "Odpowiadaj WYŁĄCZNIE w formacie JSON:\n"
            "Jeśli chcesz użyć narzędzia:\n"
            '{"thought": "twoje rozumowanie", "tool": "nazwa_narzedzia", "input": {"param": "wartość"}}\n\n'
            "Jeśli masz gotową odpowiedź:\n"
            '{"thought": "twoje rozumowanie", "tool": "FINISH", "answer": "finalna odpowiedź"}'
        )

    @staticmethod
    def _parse_json(text: str) -> dict:
        """Próbuje sparsować JSON z odpowiedzi modelu."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # fallback: wytnij pierwszy blok JSON z tekstu
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {"thought": text, "tool": "FINISH", "answer": text}
