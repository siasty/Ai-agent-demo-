"""
Anonimizacja danych – dwa tryby:

1. DataAnonymizer      – maskowanie nieodwracalne (do zakładki demo)
2. ReversibleAnonymizer – tokenizacja ODWRACALNA (do pipeline’u agenta)

ReversibleAnonymizer – przykład:
    text = "Jan Kowalski, jan@firma.pl, PESEL: 85071234567"

    encode(text) → (
        "[NAME_1] [NAME_2], [EMAIL_1], PESEL: [PESEL_1]",
        {
            "[NAME_1]":  "Jan",
            "[NAME_2]":  "Kowalski",
            "[EMAIL_1]": "jan@firma.pl",
            "[PESEL_1]": "85071234567",
        }
    )

    decode("Cześć [NAME_1], Twój email [EMAIL_1] jest OK", mapa) →
        "Cześć Jan, Twój email jan@firma.pl jest OK"

    LLM NIGDY nie widzi oryginalnych danych – widzi tylko tokeny.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod


# ===========================================================================
# Strategie (współdzielone przez oba anonimizatory)
# ===========================================================================

class AnonymizationStrategy(ABC):
    @abstractmethod
    def get_pattern(self) -> str: ...
    @abstractmethod
    def anonymize(self, text: str) -> str: ...


class EmailAnonymizer(AnonymizationStrategy):
    _P = r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
    def get_pattern(self) -> str: return self._P
    def anonymize(self, text: str) -> str:
        def _mask(m):
            local, domain = m.group().split("@", 1)
            masked = local[0] + "*" * (len(local) - 2) + local[-1] if len(local) > 2 else "***"
            return f"{masked}@{domain}"
        return re.sub(self._P, _mask, text)


class PhoneAnonymizer(AnonymizationStrategy):
    _P = r"\b(\+?48)?[\s\-]?(\d{3})[\s\-]?(\d{3})[\s\-]?(\d{3})\b"
    def get_pattern(self) -> str: return self._P
    def anonymize(self, text: str) -> str:
        return re.sub(self._P, r"\2-***-***", text)


class PeselAnonymizer(AnonymizationStrategy):
    _P = r"\b\d{11}\b"
    def get_pattern(self) -> str: return self._P
    def anonymize(self, text: str) -> str:
        return re.sub(self._P, lambda m: m.group()[:6] + "*****", text)


class NameAnonymizer(AnonymizationStrategy):
    _NAMES = [
        "Adam","Anna","Marek","Maria","Piotr","Katarzyna","Tomasz","Agnieszka",
        "Krzysztof","Barbara","Andrzej","Ewa","Janusz","Elżbieta","Stanisław",
        "Zofia","Michał","Małgorzata","Dariusz","Teresa","Jan","Paweł",
        "Monika","Grzegorz","Joanna","Marta","Kowalski","Nowak","Wiśniewska",
    ]
    def get_pattern(self) -> str:
        return rf"\b({'|'.join(re.escape(n) for n in self._NAMES)})\b"
    def anonymize(self, text: str) -> str:
        return re.sub(self.get_pattern(), "[IMIĘ]", text)


# ===========================================================================
# 1. DataAnonymizer – maskowanie nieodwracalne (zakładka demo)
# ===========================================================================

class DataAnonymizer:
    """
    Maskuje dane na stałe (nieodwracalnie).
    Używany w zakładce „Anonimizacja Danych” jako demo samego mechanizmu.
    """
    _MAP   = {"email": EmailAnonymizer, "phone": PhoneAnonymizer,
               "pesel": PeselAnonymizer, "name": NameAnonymizer}
    _ORDER = ["pesel", "email", "phone", "name"]

    def __init__(self):
        self._s = {k: cls() for k, cls in self._MAP.items()}

    def anonymize(self, text: str, data_types: list[str] | None = None) -> str:
        result, applied = text, []
        for dt in self._order(data_types):
            new = self._s[dt].anonymize(result)
            if new != result: applied.append(dt)
            result = new
        suffix = f"\n\n[Zanonimizowano: {', '.join(applied)}]" if applied else "\n\n[Brak danych]"
        return result + suffix

    def preview(self, text: str) -> dict[str, int]:
        return {n: len(list(re.finditer(s.get_pattern(), text)))
                for n, s in self._s.items()
                if re.search(s.get_pattern(), text)}

    def anonymize_verbose(self, text: str, data_types: list[str] | None = None) -> dict:
        result, changes = text, []
        for dt in self._order(data_types):
            s = self._s[dt]
            found = [m.group() for m in re.finditer(s.get_pattern(), result)]
            new = s.anonymize(result)
            if new != result and found:
                changes.append({"type": dt, "count": len(found),
                                 "samples": [{"original": f, "anonymized": s.anonymize(f)} for f in found[:3]]})
            result = new
        return {"original": text, "anonymized": result, "changes": changes}

    def _order(self, dt):
        return self._ORDER if dt is None else [t for t in self._ORDER if t in dt]


# ===========================================================================
# 2. ReversibleAnonymizer – tokenizacja ODWRACALNA (pipeline agenta)
# ===========================================================================

class ReversibleAnonymizer:
    """
    Zastępuje PII tokenami [TYPE_N] i pozwala je później odkodować.

    Główny mechanizm ochrony prywatności w pipeline’u agenta:
        - encode() → LLM widzi tylko [EMAIL_1], [PESEL_1] itp.
        - decode() → odpowiedź LLM jest odkodowywana przed pokazaniem użytkownikowi
    """
    _PREFIXES = {"pesel": "PESEL", "email": "EMAIL", "phone": "PHONE", "name": "NAME"}
    _ORDER    = ["pesel", "email", "phone", "name"]

    def __init__(self):
        self._s = {
            "pesel": PeselAnonymizer(),
            "email": EmailAnonymizer(),
            "phone": PhoneAnonymizer(),
            "name":  NameAnonymizer(),
        }

    def encode(self, text: str, data_types: list[str] | None = None) -> tuple[str, dict[str, str]]:
        """
        Koduje PII w tekście na tokeny.

        Zwraca:
            encoded_text – tekst z tokenami zamiast PII
            token_map    – {"[EMAIL_1]": "jan@firma.pl", ...} (przechowywany lokalnie)
        """
        types = self._order(data_types)
        result   = text
        token_map: dict[str, str] = {}
        counters: dict[str, int]  = {}

        for dtype in types:
            strategy = self._s.get(dtype)
            if not strategy:
                continue

            prefix  = self._PREFIXES[dtype]
            pattern = strategy.get_pattern()

            # zamknij dtype/prefix w domyślnych argumentach, żeby uniknąć pętli closure
            def _replace(match, _dt=dtype, _pre=prefix):
                original            = match.group()
                counters[_dt]       = counters.get(_dt, 0) + 1
                token               = f"[{_pre}_{counters[_dt]}]"
                token_map[token]    = original
                return token

            result = re.sub(pattern, _replace, result)

        return result, token_map

    def decode(self, text: str, token_map: dict[str, str]) -> str:
        """
        Odkodowuje tokeny → oryginalne wartości.
        Wywoływane na odpowiedzi LLM przed pokazaniem użytkownikowi.
        """
        result = text
        for token, original in token_map.items():
            result = result.replace(token, original)
        return result

    def preview(self, text: str) -> dict[str, int]:
        """Wykrywa PII bez modyfikacji tekstu."""
        return {n: len(list(re.finditer(s.get_pattern(), text)))
                for n, s in self._s.items()
                if re.search(s.get_pattern(), text)}

    def _order(self, dt):
        return self._ORDER if dt is None else [t for t in self._ORDER if t in dt]
