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
import spacy
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass


@dataclass
class SensitiveEntity:
    """Represents a detected sensitive data entity."""
    text: str
    label: str
    start: int
    end: int
    confidence: float = 1.0


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
            "PHONE": re.compile(r'(?:\+\d{1,3}\s?)?(?:\d{1,4}[\s-]?){2,4}\d{1,4}'),
            "IBAN": re.compile(r'\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}[A-Z0-9]{0,16}\b'),
            "SSN": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),  # US SSN format
            "CREDIT_CARD": re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'),  # Credit card
            "TAX_ID": re.compile(r'\b\d{2}-\d{7}\b'),  # General tax ID format
        }

    def _load_model(self) -> None:
        """Load spaCy model with fallback to smaller English model if needed."""
        try:
            self.nlp = spacy.load(self.model_name)
            print(f"✅ Loaded spaCy model: {self.model_name}")
        except OSError:
            print(f"⚠️ Model {self.model_name} not found, trying en_core_web_sm")
            try:
                self.nlp = spacy.load("en_core_web_sm")
                print("✅ Loaded English model: en_core_web_sm")
            except OSError:
                print("❌ No spaCy models available. Please install: python -m spacy download en_core_web_sm")
                raise

    def detect_entities(self, text: str) -> List[SensitiveEntity]:
        """
        Detect all sensitive entities in text.

        Args:
            text: Input text to analyze

        Returns:
            List of detected sensitive entities
        """
        entities = []

        # 1. spaCy NER detection
        doc = self.nlp(text)
        for ent in doc.ents:
            if self._is_sensitive_label(ent.label_):
                entities.append(SensitiveEntity(
                    text=ent.text,
                    label=ent.label_,
                    start=ent.start_char,
                    end=ent.end_char,
                    confidence=1.0  # spaCy doesn't provide confidence scores by default
                ))

        # 2. Custom pattern detection
        for pattern_name, pattern in self.custom_patterns.items():
            for match in pattern.finditer(text):
                entities.append(SensitiveEntity(
                    text=match.group(),
                    label=pattern_name,
                    start=match.start(),
                    end=match.end(),
                    confidence=1.0
                ))

        # 3. Remove overlapping entities (keep longer ones)
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

    def analyze_text_sensitivity(self, text: str) -> Dict[str, Any]:
        """
        Comprehensive analysis of text sensitivity.

        Returns:
            Dict with sensitivity analysis results
        """
        entities = self.detect_entities(text)

        # Categorize entities
        categories = {}
        for entity in entities:
            category = self._get_sensitivity_category(entity.label)
            if category not in categories:
                categories[category] = []
            categories[category].append(entity)

        # Calculate sensitivity score
        sensitivity_score = self._calculate_sensitivity_score(entities)

        return {
            "total_entities": len(entities),
            "sensitivity_score": sensitivity_score,
            "sensitivity_level": self._get_sensitivity_level(sensitivity_score),
            "categories": categories,
            "entities": [
                {
                    "text": e.text,
                    "label": e.label,
                    "start": e.start,
                    "end": e.end,
                    "category": self._get_sensitivity_category(e.label)
                }
                for e in entities
            ]
        }

    def _get_sensitivity_category(self, label: str) -> str:
        """Map entity labels to sensitivity categories."""
        category_mapping = {
            "PERSON": "personal_data",
            "ORG": "business_data",
            "GPE": "location_data",
            "LOC": "location_data",
            "MONEY": "financial_data",
            "DATE": "temporal_data",
            "TIME": "temporal_data",
            "EMAIL": "contact_data",
            "PHONE": "contact_data",
            "IBAN": "financial_data",
            "SSN": "personal_data",
            "CREDIT_CARD": "financial_data",
            "TAX_ID": "business_data",
            "CARDINAL": "numeric_data",
            "ORDINAL": "numeric_data"
        }
        return category_mapping.get(label, "other")

    def _calculate_sensitivity_score(self, entities: List[SensitiveEntity]) -> float:
        """Calculate overall sensitivity score (0-1)."""
        if not entities:
            return 0.0

        # Weight different entity types
        weights = {
            "personal_data": 1.0,
            "financial_data": 0.9,
            "contact_data": 0.8,
            "business_data": 0.7,
            "location_data": 0.5,
            "temporal_data": 0.3,
            "numeric_data": 0.2,
            "other": 0.1
        }

        total_weight = sum(
            weights.get(self._get_sensitivity_category(e.label), 0.1)
            for e in entities
        )

        # Normalize by text length and entity count
        max_possible_weight = len(entities) * 1.0
        return min(total_weight / max(max_possible_weight, 1), 1.0)

    def _get_sensitivity_level(self, score: float) -> str:
        """Convert sensitivity score to human-readable level."""
        if score >= 0.8:
            return "HIGH"
        elif score >= 0.5:
            return "MEDIUM"
        elif score >= 0.2:
            return "LOW"
        else:
            return "MINIMAL"

    def get_model_info(self) -> Dict[str, str]:
        """Get information about loaded spaCy model."""
        if not self.nlp:
            return {"error": "No model loaded"}

        return {
            "model_name": self.model_name,
            "language": self.nlp.lang,
            "pipeline": list(self.nlp.pipe_names),
            "entities": list(self.nlp.get_pipe("ner").labels) if "ner" in self.nlp.pipe_names else []
        }


def test_ner_detector():
    """Test function for the NER detector."""
    detector = SpacyNERDetector()

    test_texts = [
        "Jan Kowalski z firmy TechCorp mieszka w Warszawie. Email: jan@techcorp.pl, tel: +48 123 456 789",
        "Faktura dla Microsoft Corporation na kwotę $15,000 z dnia 2023-12-15",
        "PESEL: 85010112345, NIP: 123-456-78-90, REGON: 123456789"
    ]

    for text in test_texts:
        print(f"\n📝 Tekst: {text}")
        analysis = detector.analyze_text_sensitivity(text)
        print(f"🔍 Znalezione podmioty: {analysis['total_entities']}")
        print(f"📊 Poziom wrażliwości: {analysis['sensitivity_level']} ({analysis['sensitivity_score']:.2f})")

        for entity in analysis['entities']:
            print(f"  - {entity['text']} [{entity['label']}] -> {entity['category']}")


if __name__ == "__main__":
    test_ner_detector()