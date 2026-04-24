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
        "Paweł", "Monika", "Grzegorz", "Joanna", "Marta", "Kowalski",
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
    Kolejność ma znaczenie – PESEL przed telefonem (oba mają cyfry).
    """

    _STRATEGY_MAP: dict[str, type[AnonymizationStrategy]] = {
        "email": EmailAnonymizer,
        "phone": PhoneAnonymizer,
        "pesel": PeselAnonymizer,
        "name":  NameAnonymizer,
    }

    # PESEL przed phone – oba zawierają długie ciągi cyfr
    _DEFAULT_ORDER = ["pesel", "email", "phone", "name"]

    def __init__(self) -> None:
        self._strategies: dict[str, AnonymizationStrategy] = {
            key: cls() for key, cls in self._STRATEGY_MAP.items()
        }

    # ------------------------------------------------------------------
    # Publiczne metody
    # ------------------------------------------------------------------

    def anonymize(self, text: str, data_types: list[str] | None = None) -> str:
        """
        Anonimizuje tekst używając wybranych strategii.

        Zwraca tekst z zanonimizowanymi danymi + podsumowanie na końcu.
        """
        result = text
        applied: list[str] = []

        for dtype in self._resolve_order(data_types):
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
        """Wykrywa dane bez anonimizacji – zwraca {typ: liczba_trafień}."""
        findings: dict[str, int] = {}
        for name, strategy in self._strategies.items():
            matches = list(re.finditer(strategy.get_pattern(), text))
            if matches:
                findings[name] = len(matches)
        return findings

    def anonymize_verbose(self, text: str, data_types: list[str] | None = None) -> dict:
        """
        Anonimizuje tekst i zwraca pełny raport zmian.

        Zwraca:
            {
                "original":   str,       # tekst przed
                "anonymized": str,       # tekst po
                "changes": [
                    {
                        "type":      str,        # np. "email"
                        "count":     int,        # liczba zamian
                        "samples":   [           # max 3 przykłady
                            {"original": str, "anonymized": str}
                        ]
                    }, ...
                ]
            }
        """
        result = text
        changes: list[dict] = []

        for dtype in self._resolve_order(data_types):
            strategy = self._strategies.get(dtype)
            if not strategy:
                continue

            pattern = strategy.get_pattern()
            found_matches = [m.group() for m in re.finditer(pattern, result)]

            new_result = strategy.anonymize(result)

            if new_result != result and found_matches:
                samples = []
                for original in found_matches[:3]:
                    # Aplikuj strategię na pojedynczym ciągu, by uzyskać formę po
                    anonymized_sample = strategy.anonymize(original)
                    samples.append({
                        "original":   original,
                        "anonymized": anonymized_sample,
                    })

                changes.append({
                    "type":    dtype,
                    "count":   len(found_matches),
                    "samples": samples,
                })

            result = new_result

        return {
            "original":   text,
            "anonymized": result,
            "changes":    changes,
        }

    # ------------------------------------------------------------------
    # Pomocnicze
    # ------------------------------------------------------------------

    def _resolve_order(self, data_types: list[str] | None) -> list[str]:
        """Zwraca listę typów w ustalonej kolejności."""
        if data_types is None:
            return self._DEFAULT_ORDER
        return [t for t in self._DEFAULT_ORDER if t in data_types]
