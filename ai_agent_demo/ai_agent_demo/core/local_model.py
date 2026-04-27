"""
LocalModel – adapter do Ollamy (lokalny serwer LLM).

Ollama musi być uruchomiona: https://ollama.ai
Obsługiwane modele: llama3.2, mistral, phi3, gemma2, …
"""
from __future__ import annotations

import json
import requests


class LocalModel:
    """
    Komunikuje się z lokalnie działającym LLM przez Ollama HTTP API.

    Parametry konstruktora:
        model_name: nazwa modelu zainstalowanego w Ollama (np. "llama3.2")
    """

    OLLAMA_URL = "http://localhost:11434"
    TIMEOUT = 120

    def __init__(self, model_name: str = "llama3.2") -> None:
        self.model_name = model_name

    # ------------------------------------------------------------------
    # Publiczne metody
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Sprawdza czy Ollama działa i model jest pobrany."""
        try:
            resp = requests.get(f"{self.OLLAMA_URL}/api/tags", timeout=5)
            if resp.status_code != 200:
                return False
            models = [m["name"] for m in resp.json().get("models", [])]
            return any(self.model_name in m for m in models)
        except requests.RequestException:
            return False

    def list_models(self) -> list[str]:
        """Zwraca listę dostępnych modeli."""
        try:
            resp = requests.get(f"{self.OLLAMA_URL}/api/tags", timeout=5)
            if resp.status_code == 200:
                return [m["name"] for m in resp.json().get("models", [])]
        except requests.RequestException:
            pass
        return []

    def chat(self, system: str, messages: list[dict]) -> str:
        """
        Wysyła wiadomości do modelu i zwraca odpowiedź.

        Parametry:
            system:   treść system prompt (opis roli agenta + lista narzędzi)
            messages: historia rozmowy [{"role": "user/assistant", "content": "..."}]

        Zwraca odpowiedź modelu jako string (oczekiwany JSON).
        """
        payload = {
            "model": self.model_name,
            "system": system,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1, "top_p": 0.9},
        }
        try:
            resp = requests.post(
                f"{self.OLLAMA_URL}/api/chat",
                json=payload,
                timeout=self.TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"]
        except requests.Timeout:
            return json.dumps({
                "thought": "Model nie odpowiedział w czasie.",
                "tool": "FINISH",
                "answer": "Przekroczono limit czasu oczekiwania na model.",
            })
        except requests.RequestException as exc:
            return json.dumps({
                "thought": f"Błąd połączenia: {exc}",
                "tool": "FINISH",
                "answer": f"Błąd: {exc}",
            })
