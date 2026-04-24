"""
Anonimizacja danych – wzorzec Strategy (OOP).

Każdy typ danych osobowych ma własną strategię anonimizacji.
DataAnonymizer koordynuje ich działanie.

Hierarchia:
    AnonymizationStrategy (ABC)
    ├── EmailAnonymizer
    ├── PhoneAnonymizer
    ├── PeselAnonymizer
    └── NameAnonymizer

    DataAnonymizer  ←  używa powyższych strategii
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod


# ===========================================================================
# Interfejs bazowy – Strategy
# ===========================================================================

class AnonymizationStrategy(ABC):
    """Abstrakcyjna strategia anonimizacji jednego typu danych."""

    @abstractmethod
    def get_pattern(self) -> str:
        """Zwraca wyrażenie regularne wykrywające dane."""
        ...

    @abstractmethod
    def anonymize(self, text: str) -> str:
        """Zastępuje znalezione dane zanonimizowaną formą."""
        ...


# ===========================================================================
# Konkretne strategie
# ===========================================================================

class EmailAnonymizer(AnonymizationStrategy):
    """Maskuje adres email: jan.kowalski@firma.pl → j**********i@firma.pl"""

    _PATTERN = r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"

    def get_pattern(self) -> str:
        return self._PATTERN

    def anonymize(self, text: str) -> str:
        def _mask(match: re.Match) -> str:
            local, domain = match.group().split("@", 1)
            if len(local) <= 2:
                masked = "***"
            else:
                masked = local[0] + "*" * (len(local) - 2) + local[-1]
            return f"{masked}@{domain}"

        return re.sub(self._PATTERN, _mask, text)


class PhoneAnonymizer(AnonymizationStrategy):
    """Maskuje polskie numery telefonów: 500 100 200 → 500-***-***"""

    _PATTERN = r"\b(\+?48)?[\s\-]?(\d{3})[\s\-]?(\d{3})[\s\-]?(\d{3})\b"

    def get_pattern(self) -> str:
        return self._PATTERN

    def anonymize(self, text: str) -> str:
        return re.sub(self._PATTERN, r"\2-***-***", text)


class PeselAnonymizer(AnonymizationStrategy):
    """Maskuje PESEL: 85071234567 → 850712*****"""

    _PATTERN = r"\b\d{11}\b"

    def get_pattern(self) -> str:
        return self._PATTERN

    def anonymize(self, text: str) -> str:
        def _mask(match: re.Match) -> str:
            p = match.group()
            return p[:6] + "*" * 5

        return re.sub(self._PATTERN, _mask, text)


class NameAnonymizer(AnonymizationStrategy):
    """Zastępuje popularne polskie imiona znacznikiem [IMIĘ]."""

    _NAMES = [
        "Adam", "Anna", "Marek", "Maria", "Piotr", "Katarzyna",
        "Tomasz", "Agnieszka", "Krzysztof", "Barbara", "Andrzej",
        "Ewa", "Janusz", "Elżbieta", "Stanisław", "Zofia",
        "Michał", "Małgorzata", "Dariusz", "Teresa", "Jan",
        "Paweł", "Monika", "Grzegorz", "Joanna", "Marta",
    ]

    def get_pattern(self) -> str:
        joined = "|".join(re.escape(n) for n in self._NAMES)
        return rf"\b({joined})\b"

    def anonymize(self, text: str) -> str:
        return re.sub(self.get_pattern(), "[IMIĘ]", text)


# ===========================================================================
# Koordynator – DataAnonymizer
# ===========================================================================

class DataAnonymizer:
    """
    Główna klasa anonimizacji.

    Zarządza zbiorem strategii i aplikuje je w odpowiedniej kolejności.
    Kolejność ma znaczenie – np. PESEL przed numerem telefonu.
    """

    # Mapowanie nazwy → klasy strategii
    _STRATEGY_MAP: dict[str, type[AnonymizationStrategy]] = {
        "email": EmailAnonymizer,
        "phone": PhoneAnonymizer,
        "pesel": PeselAnonymizer,
        "name": NameAnonymizer,
    }

    # Kolejność stosowania (pesel przed phone – oba mają liczby)
    _DEFAULT_ORDER = ["pesel", "email", "phone", "name"]

    def __init__(self) -> None:
        self._strategies: dict[str, AnonymizationStrategy] = {
            key: cls() for key, cls in self._STRATEGY_MAP.items()
        }

    def anonymize(self, text: str, data_types: list[str] | None = None) -> str:
        """
        Anonimizuje tekst używając wybranych strategii.

        Parametry:
            text:       wejściowy tekst
            data_types: lista typów do anonimizacji (None = wszystkie)

        Zwraca tekst z zanonimizowanymi danymi + podsumowanie.
        """
        if data_types is None:
            data_types = self._DEFAULT_ORDER
        else:
            # zachowaj ustaloną kolejność
            data_types = [t for t in self._DEFAULT_ORDER if t in data_types]

        result = text
        applied: list[str] = []

        for dtype in data_types:
            strategy = self._strategies.get(dtype)
            if not strategy:
                continue
            new_result = strategy.anonymize(result)
            if new_result != result:
                applied.append(dtype)
            result = new_result

        summary = (
            f"\n\n[Zanonimizowano: {', '.join(applied)}]"
            if applied
            else "\n\n[Brak danych do anonimizacji]"
        )
        return result + summary

    def preview(self, text: str) -> dict[str, int]:
        """Wykrywa dane bez anonimizacji – zwraca słownik {typ: liczba_trafień}."""
        findings: dict[str, int] = {}
        for name, strategy in self._strategies.items():
            matches = re.findall(strategy.get_pattern(), text)
            if matches:
                findings[name] = len(matches)
        return findings
