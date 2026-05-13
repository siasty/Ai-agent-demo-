"""
Advanced NLP-based Sensitive Data Detection using spaCy.

Automatically detects and classifies sensitive entities:
- PERSON: People names
- ORG: Organizations, companies
- GPE: Locations (cities, countries)
- MONEY: Financial amounts
- DATE: Dates and time expressions
- EMAIL: Email addresses (custom)
- PHONE: Phone numbers (custom)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List

import spacy


@dataclass
class SensitiveEntity:
    """A detected sensitive data entity, with its char offsets in the source text."""
    text: str
    label: str
    start: int
    end: int


class SpacyNERDetector:
    """Advanced NER-based sensitive data detector using spaCy."""

    def __init__(self, model_name: str = "en_core_web_sm"):
        """
        Initialize with English language model.

        Args:
            model_name: spaCy model name (en_core_web_sm for English)
        """
        self.model_name = model_name
        self.nlp = None
        self._load_model()

        # Custom patterns for business data
        self.custom_patterns = {
            "EMAIL": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            "PHONE": re.compile(r'(?:\+\d{1,3}[\s-]?)?(?:\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{4}|\d{1,3}[\s-]\d{3}[\s-]\d{4})'),  # Phone numbers with country codes
            "ORG": re.compile(r'\b[A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*)*\s+(?:Inc|Corp|LLC|Ltd|Company|Corporation|Partners|Group|Associates|Solutions|Technologies|Services|Systems)\b'),  # Company names
            "FACILITY": re.compile(r'\b[A-Z][A-Za-z]*\s+(?:Center|Centre|Building|Tower|Plaza|Complex|Campus|Park|Office|Facility|Mall|Square)\b'),  # Building/facility names
            "ZIPCODE": re.compile(r'\b\d{5}(?:-\d{4})?\b'),  # US ZIP codes (5 or 9 digits)
            "IBAN": re.compile(r'\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}[A-Z0-9]{0,16}\b'),
            "SSN": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),  # US SSN format
            "CREDIT_CARD": re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'),  # Credit card
            "TAX_ID": re.compile(r'\b\d{2}-\d{7}\b'),  # General tax ID format
        }

    def _load_model(self) -> None:
        """Load spaCy model, falling back to en_core_web_sm if the requested one is missing."""
        try:
            self.nlp = spacy.load(self.model_name)
        except OSError:
            self.nlp = spacy.load("en_core_web_sm")
            self.model_name = "en_core_web_sm"

    def detect_entities(self, text: str) -> List[SensitiveEntity]:
        """Detect all sensitive entities in text via spaCy NER + custom regex patterns."""
        entities: List[SensitiveEntity] = []

        # 1. spaCy NER
        for ent in self.nlp(text).ents:
            if self._is_sensitive_label(ent.label_):
                entities.append(SensitiveEntity(
                    text=ent.text,
                    label=ent.label_,
                    start=ent.start_char,
                    end=ent.end_char,
                ))

        # 2. Custom regex patterns
        for pattern_name, pattern in self.custom_patterns.items():
            for match in pattern.finditer(text):
                entities.append(SensitiveEntity(
                    text=match.group(),
                    label=pattern_name,
                    start=match.start(),
                    end=match.end(),
                ))

        entities = self._filter_false_positives(entities)
        entities = self._remove_overlaps(entities)
        return sorted(entities, key=lambda e: e.start)

    def _is_sensitive_label(self, label: str) -> bool:
        """Check if spaCy entity label indicates sensitive data."""
        sensitive_labels = {
            "PERSON",  # Person names
            "ORG",     # Organizations
            "GPE",     # Geopolitical entities (cities, countries)
            "LOC",     # Locations
            "MONEY",   # Monetary values
            "DATE",    # Dates
            "TIME",    # Times
            "CARDINAL", # Numbers that might be sensitive
            "ORDINAL",  # Ordinal numbers
        }
        return label in sensitive_labels

    def _filter_false_positives(self, entities: List[SensitiveEntity]) -> List[SensitiveEntity]:
        """Filter out false detections that are likely just technical terms or numbers."""
        filtered = []

        # Technical terms that shouldn't be considered sensitive
        technical_terms = {
            'lcd display', 'display', 'monitor', 'screen', 'processor', 'intel processor',
            'cisco', 'dell', 'microsoft', 'apple', 'google', 'server', 'networking',
            'technology', 'advanced', 'character lcd display', 'lcd', 'character display'
        }

        for entity in entities:
            entity_lower = entity.text.lower().strip()

            # Skip standalone numbers detected as DATE (likely address numbers, years without context, etc.)
            if entity.label == "DATE" and entity.text.strip().isdigit() and len(entity.text.strip()) <= 5:
                continue

            # Skip CARDINAL (numbers) that are likely technical specifications
            if entity.label == "CARDINAL" and ('x' in entity_lower or len(entity.text.strip()) <= 4):
                continue

            # Skip technical terms falsely detected as PERSON
            if entity.label == "PERSON" and entity_lower in technical_terms:
                continue

            # Skip technical terms falsely detected as ORG (organizations)
            if entity.label == "ORG" and entity_lower in technical_terms:
                continue

            # Skip technical terms falsely detected as ORG if they contain technical keywords
            if entity.label == "ORG" and any(term in entity_lower for term in technical_terms):
                continue

            filtered.append(entity)
        return filtered

    def _remove_overlaps(self, entities: List[SensitiveEntity]) -> List[SensitiveEntity]:
        """Remove overlapping entities, keeping longer ones."""
        if not entities:
            return entities

        # Sort by start position
        sorted_entities = sorted(entities, key=lambda e: (e.start, e.end))
        filtered = [sorted_entities[0]]

        for current in sorted_entities[1:]:
            last = filtered[-1]

            # Check if current overlaps with last
            if current.start < last.end:
                # Keep the longer entity
                if (current.end - current.start) > (last.end - last.start):
                    filtered[-1] = current
                # If same length, prefer custom patterns over spaCy
                elif (current.end - current.start) == (last.end - last.start):
                    if current.label in self.custom_patterns:
                        filtered[-1] = current
            else:
                filtered.append(current)

        return filtered

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about loaded spaCy model."""
        if not self.nlp:
            return {"error": "No model loaded"}

        return {
            "model_name": self.model_name,
            "language": self.nlp.lang,
            "pipeline": list(self.nlp.pipe_names),
            "entities": list(self.nlp.get_pipe("ner").labels) if "ner" in self.nlp.pipe_names else []
        }


