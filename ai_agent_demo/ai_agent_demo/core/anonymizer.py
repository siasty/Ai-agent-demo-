"""
Anonimizacja danych – dwa tryby + spaCy NER:

1. SpacyNER              – inteligentny NER (PERSON, ORG, GPE, DATE...)
2. Strategie regex       – PESEL, email, telefon (wzorce których NER nie zna)
3. DataAnonymizer        – maskowanie nieodwracalne (zakładka demo)
4. ReversibleAnonymizer  – tokenizacja ODWRACALNA (pipeline agenta)

Przepływ kodowania:
    tekst
      ↓ SpacyNER.encode()   → [PERSON_1], [ORG_1], [LOC_1] ...
      ↓ PeselStrategy       → [PESEL_1] ...
      ↓ EmailStrategy       → [EMAIL_1] ...
      ↓ PhoneStrategy       → [PHONE_1] ...
    zakodowany_tekst + token_map

LLM nigdy nie widzi oryginalnych danych osobowych.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod


# ===========================================================================
# spaCy NER – inteligentne wykrywanie encji nazwanych
# ===========================================================================

class SpacyNER:
    """
    Wykrywa encje nazwane (Named Entity Recognition) modelem spaCy.

    Model:      pl_core_news_sm  (język polski)
    Instalacja: pip install spacy
                python -m spacy download pl_core_news_sm

    Typy encji:
        PERSON  – osoby (Jan Kowalski)
        ORG     – organizacje (Firma XYZ)
        LOC/GPE – miejsca (Warszawa)
        DATE    – daty (12 marca 2025)

    Lazy loading – model ładuje się raz przy pierwszym użyciu.
    Jeśli model nie jest zainstalowany, NER jest pomijany.
    """

    # Mapowanie etykiet spaCy → nasze prefiksy tokenów
    _LABEL_MAP = {
        "persName": "PERSON",
        "PERSON":   "PERSON",
        "orgName":  "ORG",
        "ORG":      "ORG",
        "placeName":"LOC",
        "GPE":      "LOC",
        "LOC":      "LOC",
        "DATE":     "DATE",
        "TIME":     "TIME",
    }

    _MODEL   = "pl_core_news_sm"
    _nlp_ref = None  # singleton – jeden model dla całej aplikacji

    @classmethod
    def _get_nlp(cls):
        """Zwraca załadowany model lub None jeśli niedostępny."""
        if cls._nlp_ref is None:
            try:
                import spacy          # noqa: PLC0415
                cls._nlp_ref = spacy.load(cls._MODEL)
            except (ImportError, OSError):
                cls._nlp_ref = False  # sentinel: próbowaliśmy, nie ma modelu
        return cls._nlp_ref or None

    @classmethod
    def is_available(cls) -> bool:
        """Czy model spaCy jest zainstalowany i dostępny?"""
        return cls._get_nlp() is not None

    @classmethod
    def detect(cls, text: str) -> list[dict]:
        """
        Wykrywa encje bez modyfikacji tekstu.

        Zwraca:
            [{"text": "Jan Kowalski", "label": "PERSON", "start": 0, "end": 12}, ...]
        """
        nlp = cls._get_nlp()
        if not nlp:
            return []
        doc = nlp(text)
        return [
            {
                "text":  ent.text,
                "label": cls._LABEL_MAP.get(ent.label_, ent.label_),
                "start": ent.start_char,
                "end":   ent.end_char,
            }
            for ent in doc.ents
        ]

    @classmethod
    def encode(cls, text: str, counters: dict, token_map: dict) -> str:
        """
        Zastępuje encje tokenami [LABEL_N].
        Modyfikuje counters i token_map in-place.
        Przetwarza od końca, żeby nie psuć pozycji znaków.
        """
        nlp = cls._get_nlp()
        if not nlp:
            return text

        doc    = nlp(text)
        result = text

        for ent in reversed(doc.ents):
            label              = cls._LABEL_MAP.get(ent.label_, ent.label_)
            counters[label]    = counters.get(label, 0) + 1
            token              = f"[{label}_{counters[label]}]"
            token_map[token]   = ent.text
            result             = result[: ent.start_char] + token + result[ent.end_char :]

        return result


# ===========================================================================
# Strategie regex – wzorce strukturalne (PESEL, email, telefon)
# ===========================================================================

class RegexStrategy(ABC):
    """Interfejs bazowy dla strategii opartych na wyrażeniach regularnych."""
    @abstractmethod
    def get_pattern(self) -> str: ...
    @abstractmethod
    def anonymize(self, text: str) -> str: ...


class EmailStrategy(RegexStrategy):
    """jan.kowalski@firma.pl → j**********i@firma.pl"""
    _P = r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
    def get_pattern(self) -> str: return self._P
    def anonymize(self, text: str) -> str:
        def _mask(m):
            local, domain = m.group().split("@", 1)
            masked = (local[0] + "*" * (len(local) - 2) + local[-1]) if len(local) > 2 else "***"
            return f"{masked}@{domain}"
        return re.sub(self._P, _mask, text)


class PhoneStrategy(RegexStrategy):
    """500 100 200 → 500-***-***"""
    _P = r"\b(\+?48)?[\s\-]?(\d{3})[\s\-]?(\d{3})[\s\-]?(\d{3})\b"
    def get_pattern(self) -> str: return self._P
    def anonymize(self, text: str) -> str:
        return re.sub(self._P, r"\2-***-***", text)


class PeselStrategy(RegexStrategy):
    """85071234567 → 850712*****"""
    _P = r"\b\d{11}\b"
    def get_pattern(self) -> str: return self._P
    def anonymize(self, text: str) -> str:
        return re.sub(self._P, lambda m: m.group()[:6] + "*****", text)


class NameFallbackStrategy(RegexStrategy):
    """Fallback – używany gdy spaCy niedostępne."""
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


# Aliasy dla kompatybilności wstecznej
EmailAnonymizer      = EmailStrategy
PhoneAnonymizer      = PhoneStrategy
PeselAnonymizer      = PeselStrategy
NameAnonymizer       = NameFallbackStrategy
AnonymizationStrategy = RegexStrategy


# ===========================================================================
# 1. DataAnonymizer – maskowanie nieodwracalne (zakładka demo)
# ===========================================================================

class DataAnonymizer:
    """
    Maskuje dane na stałe (nieodwracalnie).
    Używa spaCy NER + regex jako fallback.
    """
    _REGEX_ORDER = ["pesel", "email", "phone", "name"]
    _REGEX_MAP: dict[str, RegexStrategy] = {
        "email": EmailStrategy(),
        "phone": PhoneStrategy(),
        "pesel": PeselStrategy(),
        "name":  NameFallbackStrategy(),
    }

    def anonymize(self, text: str, data_types: list[str] | None = None) -> str:
        result  = text
        applied: list[str] = []

        # spaCy NER
        if SpacyNER.is_available():
            entities = SpacyNER.detect(result)
            if entities:
                for ent in sorted(entities, key=lambda e: e["start"], reverse=True):
                    result = result[: ent["start"]] + f"[{ent['label']}]" + result[ent["end"] :]
                applied.append("spacy_ner")

        # Regex
        for dt in self._resolve(data_types):
            if dt == "name" and SpacyNER.is_available():
                continue
            s   = self._REGEX_MAP[dt]
            new = s.anonymize(result)
            if new != result:
                applied.append(dt)
            result = new

        suffix = f"\n\n[Zanonimizowano: {', '.join(applied)}]" if applied else "\n\n[Brak danych]"
        return result + suffix

    def preview(self, text: str) -> dict[str, int]:
        findings: dict[str, int] = {}
        for ent in SpacyNER.detect(text):
            findings[ent["label"]] = findings.get(ent["label"], 0) + 1
        for name, s in self._REGEX_MAP.items():
            if name == "name" and SpacyNER.is_available():
                continue
            count = len(list(re.finditer(s.get_pattern(), text)))
            if count:
                findings[name] = findings.get(name, 0) + count
        return findings

    def anonymize_verbose(self, text: str, data_types: list[str] | None = None) -> dict:
        result  = text
        changes: list[dict] = []

        if SpacyNER.is_available():
            entities = SpacyNER.detect(result)
            if entities:
                samples = [{"original": e["text"], "anonymized": f"[{e['label']}]"} for e in entities[:4]]
                changes.append({"type": "spacy_ner", "count": len(entities), "samples": samples})
                for ent in sorted(entities, key=lambda e: e["start"], reverse=True):
                    result = result[: ent["start"]] + f"[{ent['label']}]" + result[ent["end"] :]

        for dt in self._resolve(data_types):
            if dt == "name" and SpacyNER.is_available():
                continue
            s     = self._REGEX_MAP[dt]
            found = [m.group() for m in re.finditer(s.get_pattern(), result)]
            new   = s.anonymize(result)
            if new != result and found:
                changes.append({"type": dt, "count": len(found),
                                 "samples": [{"original": f, "anonymized": s.anonymize(f)} for f in found[:3]]})
            result = new

        return {"original": text, "anonymized": result, "changes": changes}

    def _resolve(self, dt):
        return self._REGEX_ORDER if dt is None else [t for t in self._REGEX_ORDER if t in dt]


# ===========================================================================
# 2. ReversibleAnonymizer – tokenizacja ODWRACALNA (pipeline agenta)
# ===========================================================================

class ReversibleAnonymizer:
    """
    Zastępuje PII tokenami [TYPE_N] i pozwala je później odkodować.

    Kolejność kodowania:
        1. spaCy NER  → [PERSON_1], [ORG_1], [LOC_1] ...
        2. Regex      → [PESEL_1], [EMAIL_1], [PHONE_1] ...
           (fallback: [NAME_1] gdy spaCy niedostępne)

    decode() przywraca oryginalne wartości po odpowiedzi LLM.
    LLM NIGDY nie widzi oryginalnych danych.
    """

    _REGEX_PREFIXES = {"pesel": "PESEL", "email": "EMAIL", "phone": "PHONE", "name": "NAME"}
    _REGEX_ORDER    = ["pesel", "email", "phone", "name"]
    _REGEX_STRATS: dict[str, RegexStrategy] = {
        "pesel": PeselStrategy(),
        "email": EmailStrategy(),
        "phone": PhoneStrategy(),
        "name":  NameFallbackStrategy(),
    }

    def encode(self, text: str, data_types: list[str] | None = None) -> tuple[str, dict[str, str]]:
        """
        Koduje PII → tokeny.

        Zwraca:
            encoded_text  – tekst z tokenami zamiast PII
            token_map     – {"[PERSON_1]": "Jan Kowalski", ...}
        """
        result    = text
        token_map: dict[str, str] = {}
        counters:  dict[str, int] = {}

        # Krok 1: spaCy NER (PERSON, ORG, GPE, DATE...)
        result = SpacyNER.encode(result, counters, token_map)

        # Krok 2: Regex (PESEL, email, telefon; imiona gdy spaCy niedostępne)
        for dtype in self._resolve(data_types):
            if dtype == "name" and SpacyNER.is_available():
                continue

            strategy = self._REGEX_STRATS.get(dtype)
            if not strategy:
                continue

            prefix  = self._REGEX_PREFIXES[dtype]
            pattern = strategy.get_pattern()

            def _replace(match, _dt=dtype, _pre=prefix):
                original          = match.group()
                counters[_dt]     = counters.get(_dt, 0) + 1
                token             = f"[{_pre}_{counters[_dt]}]"
                token_map[token]  = original
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
        """Wykrywa PII bez modyfikacji – zwraca {typ: liczba}."""
        findings: dict[str, int] = {}
        for ent in SpacyNER.detect(text):
            findings[ent["label"]] = findings.get(ent["label"], 0) + 1
        for name, s in self._REGEX_STRATS.items():
            if name == "name" and SpacyNER.is_available():
                continue
            count = len(list(re.finditer(s.get_pattern(), text)))
            if count:
                findings[name] = findings.get(name, 0) + count
        return findings

    def _resolve(self, dt):
        return self._REGEX_ORDER if dt is None else [t for t in self._REGEX_ORDER if t in dt]
