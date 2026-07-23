"""
Business Data Pseudonymization Engine.

Replaces sensitive business data with consistent pseudonyms while preserving relationships.
Example: "Jan Kowalski" → "CUSTOMER_42" (same mapping throughout document)

Enhanced with spaCy NLP for automatic sensitive data detection.
"""
from __future__ import annotations

import re
import hashlib
from typing import Dict, Any, Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .ner_detector import SpacyNERDetector, SensitiveEntity

try:
    from .ner_detector import SpacyNERDetector, SensitiveEntity
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    SpacyNERDetector = None
    SensitiveEntity = None


class BusinessPseudonymizer:
    """Pseudonymizes business data while preserving relationships."""

    def __init__(self, use_ner: bool = True):
        """
        Initialize pseudonymizer.

        Args:
            use_ner: Enable automatic NER-based detection (requires spaCy)
        """
        self.mapping: Dict[str, str] = {}
        self.reverse_mapping: Dict[str, str] = {}
        self.counters: Dict[str, int] = {
            "customer": 0,
            "email": 0,
            "phone": 0,
            "address": 0,
            "person": 0,
            "company": 0,
            "product": 0,
            "organization": 0,
            "location": 0,
            "financial": 0,
            "sales_order": 0,
            "invoice": 0,
        }

        # Initialize NER detector if available and requested
        self.ner_detector: Optional['SpacyNERDetector'] = None
        self.use_ner = use_ner and SPACY_AVAILABLE

        # Track which methods were actually used during pseudonymization
        self._used_manual_patterns = False
        self._used_regex_fallback = False
        self._used_spacy_ner = False

        if self.use_ner:
            try:
                self.ner_detector = SpacyNERDetector()
            except Exception as e:
                import frappe
                frappe.log_error(f"Failed to initialize SpacyNERDetector: {str(e)}")
                self.use_ner = False

    def _generate_token(self, data_type: str, original: str) -> str:
        """Generate consistent pseudonym for given data."""
        # Use hash to ensure same input always gets same token
        hash_input = f"{data_type}:{original.lower()}"
        hash_hex = hashlib.md5(hash_input.encode()).hexdigest()[:6]

        if original in self.mapping:
            return self.mapping[original]

        self.counters[data_type] += 1
        token = f"{data_type.upper()}_{self.counters[data_type]:02d}"

        self.mapping[original] = token
        self.reverse_mapping[token] = original
        return token

    def _pseudonymize_company_name(self, name: str) -> str:
        """Pseudonymize company names."""
        # Keep legal forms but replace names
        legal_forms = ["Sp. z o.o.", "S.A.", "LLC", "Ltd", "Inc", "GmbH", "Corp"]

        for form in legal_forms:
            if form in name:
                base_name = name.replace(form, "").strip()
                token = self._generate_token("company", base_name)
                return f"{token} {form}"

        return self._generate_token("company", name)

    def _pseudonymize_person_name(self, name: str) -> str:
        """Pseudonymize person names."""
        return self._generate_token("person", name)

    def _pseudonymize_document_id(self, value: str, data_type: str) -> str:
        """Replace an ERP document ID before a payload reaches any LLM."""
        if not value:
            return ""
        if data_type not in {"sales_order", "invoice"}:
            raise ValueError("Unsupported ERP document identifier type.")
        return self._generate_token(data_type, value)

    def _pseudonymize_email(self, email: str) -> str:
        """Pseudonymize email addresses."""
        if "@" in email:
            local, domain = email.split("@", 1)
            domain_parts = domain.split(".")

            # Pseudonymize local part and company domain, keep TLD
            local_token = self._generate_token("email", local)
            if len(domain_parts) >= 2:
                company_token = self._generate_token("company", domain_parts[0])
                tld = domain_parts[-1]
                return f"{local_token}@{company_token}.{tld}"

        return self._generate_token("email", email)

    def _pseudonymize_phone(self, phone: str) -> str:
        """Pseudonymize phone numbers."""
        # Keep country code format but replace digits
        if phone.startswith("+48"):
            token = self._generate_token("phone", phone)
            return f"+48 {self.counters['phone']:03d} {self.counters['phone']:03d} {self.counters['phone']:03d}"
        return self._generate_token("phone", phone)

    def _pseudonymize_address(self, address: str) -> str:
        """Pseudonymize addresses while keeping structure."""
        # Keep postal codes and major cities, replace street details
        city_mapping = {
            "Warszawa": "CITY_A",
            "Kraków": "CITY_B",
            "Gdańsk": "CITY_C",
            "Wrocław": "CITY_D",
            "Poznań": "CITY_E"
        }

        result = address
        for city, pseudonym in city_mapping.items():
            if city in result:
                result = result.replace(city, pseudonym)

        # Replace street names but keep numbers and structure
        street_pattern = r'ul\.\s+[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż\s]+\s+(\d+)'
        if re.search(street_pattern, result):
            token = self._generate_token("address", address)
            # Keep the pattern but replace street name
            result = re.sub(street_pattern, f'ul. STREET_{self.counters["address"]:02d} \\1', result)

        return result

    def _pseudonymize_product(self, sku: str, description: str) -> tuple[str, str]:
        """Pseudonymize product SKU and description."""
        # Keep product family/category hints
        if "MED-" in sku:
            sku_token = f"PRODUCT_MED_{self.counters['product']:02d}"
        else:
            sku_token = self._generate_token("product", sku)

        # Generalize description
        desc_token = f"Medical device type {self.counters['product']:02d}"

        self.mapping[sku] = sku_token
        self.mapping[description] = desc_token
        self.reverse_mapping[sku_token] = sku
        self.reverse_mapping[desc_token] = description

        return sku_token, desc_token

    def pseudonymize_sales_order(self, sales_order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Automated sales order pseudonymization using spaCy NER.

        Demonstrates pure AI/NLP approach to sensitive data detection.
        """
        if self.use_ner and self.ner_detector:
            # PURE SPACY APPROACH: Extract all text and let AI analyze it
            return self._pseudonymize_with_spacy_only(sales_order)
        else:
            # Fallback to manual approach when spaCy not available
            return self._pseudonymize_with_manual_patterns(sales_order)

    def pseudonymize_customer_data(self, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pseudonymize customer credit data using spaCy NER or manual patterns.

        Args:
            customer_data: Customer data structure with credit history

        Returns:
            Pseudonymized customer data
        """
        if self.use_ner and self.ner_detector:
            return self._pseudonymize_customer_with_spacy(customer_data)
        else:
            return self._pseudonymize_customer_with_manual_patterns(customer_data)

    def _pseudonymize_customer_with_spacy(self, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Pseudonymize customer data using spaCy NER."""
        self._used_spacy_ner = True

        result = {}

        # Reporting currency for every amount below - not sensitive, must survive
        result["currency"] = customer_data.get("currency", "")

        # Customer information
        customer = customer_data.get("customer", {})
        result["customer"] = {
            "name": self.pseudonymize_text_auto(customer.get("name", "")),
            "tax_id": self.pseudonymize_text_auto(customer.get("tax_id", "")),
            "email": self.pseudonymize_text_auto(customer.get("email", "")),
            "phone": self.pseudonymize_text_auto(customer.get("phone", "")),
            "address": self.pseudonymize_text_auto(customer.get("address", "")),
            "credit_limit": customer.get("credit_limit"),  # Numeric - safe
            "customer_group": customer.get("customer_group"),  # Business category - safe
            "territory": customer.get("territory")  # Geographic region - safe
        }

        # Payment history (mostly numeric, safe)
        result["payment_history"] = customer_data.get("payment_history", {})

        # Recent orders
        recent_orders = customer_data.get("recent_orders", [])
        result["recent_orders"] = []
        for order in recent_orders:
            result["recent_orders"].append({
                "sales_order_id": self._pseudonymize_document_id(
                    order.get("sales_order_id", ""),
                    "sales_order",
                ),
                "date": order.get("date", ""),  # Dates are safe
                "amount": order.get("amount"),  # Numeric - safe
                "currency": order.get("currency", ""),  # Safe
                "discount_percent": order.get("discount_percent"),  # Safe
                "payment_terms": order.get("payment_terms", ""),  # Business term - safe
                "sales_rep": self._pseudonymize_person_name(order.get("sales_rep", ""))
            })

        # Outstanding invoices
        outstanding = customer_data.get("outstanding_invoices", [])
        result["outstanding_invoices"] = []
        for invoice in outstanding:
            result["outstanding_invoices"].append({
                "invoice_id": self._pseudonymize_document_id(
                    invoice.get("invoice_id", ""),
                    "invoice",
                ),
                "issue_date": invoice.get("issue_date", ""),  # Safe
                "due_date": invoice.get("due_date", ""),  # Safe
                "amount": invoice.get("amount"),  # Safe
                "outstanding": invoice.get("outstanding"),  # Safe
                "days_overdue": invoice.get("days_overdue"),  # Safe
                "currency": invoice.get("currency", "")  # Safe
            })

        return result

    def _pseudonymize_customer_with_manual_patterns(self, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Pseudonymize customer data using manual patterns."""
        self._used_manual_patterns = True

        result = {}

        # Reporting currency for every amount below - not sensitive, must survive
        result["currency"] = customer_data.get("currency", "")

        # Customer information
        customer = customer_data.get("customer", {})
        result["customer"] = {
            "name": self._pseudonymize_company_name(customer.get("name", "")),
            "tax_id": self._generate_token("company", customer.get("tax_id", "")),
            "email": self._pseudonymize_email(customer.get("email", "")),
            "phone": self._pseudonymize_phone(customer.get("phone", "")),
            "address": self._pseudonymize_address(customer.get("address", "")),
            "credit_limit": customer.get("credit_limit"),
            "customer_group": customer.get("customer_group"),
            "territory": customer.get("territory")
        }

        # Payment history (mostly numeric, safe)
        result["payment_history"] = customer_data.get("payment_history", {})

        # Recent orders
        recent_orders = customer_data.get("recent_orders", [])
        result["recent_orders"] = []
        for order in recent_orders:
            result["recent_orders"].append({
                "sales_order_id": self._pseudonymize_document_id(
                    order.get("sales_order_id", ""),
                    "sales_order",
                ),
                "date": order.get("date", ""),
                "amount": order.get("amount"),
                "currency": order.get("currency", ""),
                "discount_percent": order.get("discount_percent"),
                "payment_terms": order.get("payment_terms", ""),
                "sales_rep": self._pseudonymize_person_name(order.get("sales_rep", ""))
            })

        # Outstanding invoices
        outstanding = customer_data.get("outstanding_invoices", [])
        result["outstanding_invoices"] = []
        for invoice in outstanding:
            result["outstanding_invoices"].append({
                "invoice_id": self._pseudonymize_document_id(
                    invoice.get("invoice_id", ""),
                    "invoice",
                ),
                "issue_date": invoice.get("issue_date", ""),
                "due_date": invoice.get("due_date", ""),
                "amount": invoice.get("amount"),
                "outstanding": invoice.get("outstanding"),
                "days_overdue": invoice.get("days_overdue"),
                "currency": invoice.get("currency", "")
            })

        return result

    def _pseudonymize_with_spacy_only(self, sales_order: Dict[str, Any]) -> Dict[str, Any]:
        """Pure spaCy NER pseudonymization - full AI automation."""
        self._used_spacy_ner = True

        result = {}

        result["sales_order_id"] = self._pseudonymize_document_id(
            sales_order.get("sales_order_id", ""),
            "sales_order",
        )

        # Use spaCy to pseudonymize ALL text fields automatically
        customer = sales_order.get("customer", {})
        result["customer"] = {
            "name": self.pseudonymize_text_auto(customer.get("name", "")),
            "tax_id": self.pseudonymize_text_auto(customer.get("tax_id", "")),
            "email": self.pseudonymize_text_auto(customer.get("email", "")),
            "phone": self.pseudonymize_text_auto(customer.get("phone", "")),
            "address": self.pseudonymize_text_auto(customer.get("address", "")),
            "credit_limit": customer.get("credit_limit"),  # Numeric - safe
            "current_exposure": customer.get("current_exposure"),  # Numeric - safe
            "payment_terms": customer.get("payment_terms")  # Business term - safe
        }

        sales_rep = sales_order.get("sales_rep", {})
        result["sales_rep"] = {
            "name": self.pseudonymize_text_auto(sales_rep.get("name", "")),
            "email": self.pseudonymize_text_auto(sales_rep.get("email", ""))
        }

        order = sales_order.get("order", {})
        result["order"] = {
            "currency": order.get("currency"),  # Safe
            "total_net": order.get("total_net"),  # Safe
            "requested_delivery_date": order.get("requested_delivery_date"),  # Safe
            "shipping_address": self.pseudonymize_text_auto(order.get("shipping_address", "")),
            "discount_percent": order.get("discount_percent"),  # Safe
            "historical_avg_discount_percent": order.get("historical_avg_discount_percent")  # Safe
        }

        # Items - pseudonymize descriptions but keep SKUs and numbers
        items = sales_order.get("items", [])
        result["items"] = []
        for item in items:
            result["items"].append({
                "sku": item.get("sku", ""),  # Keep SKUs - they're product codes, not personal data
                "description": self.pseudonymize_text_auto(item.get("description", "")),
                "quantity": item.get("quantity"),  # Safe
                "unit_price": item.get("unit_price"),  # Safe
                "unit_cost": item.get("unit_cost"),  # Safe
                "margin_percent": item.get("margin_percent")  # Safe
            })

        # Notes - perfect for spaCy NER (free text)
        notes = sales_order.get("notes", "")
        result["notes"] = self.pseudonymize_text_auto(notes)

        return result

    def _pseudonymize_with_manual_patterns(self, sales_order: Dict[str, Any]) -> Dict[str, Any]:
        """Manual pseudonymization when spaCy not available."""
        self._used_manual_patterns = True

        result = {}

        result["sales_order_id"] = self._pseudonymize_document_id(
            sales_order.get("sales_order_id", ""),
            "sales_order",
        )

        # Manual field mapping approach
        customer = sales_order.get("customer", {})
        result["customer"] = {
            "name": self._pseudonymize_company_name(customer.get("name", "")),
            "tax_id": self._generate_token("company", customer.get("tax_id", "")),
            "email": self._pseudonymize_email(customer.get("email", "")),
            "phone": self._pseudonymize_phone(customer.get("phone", "")),
            "address": self._pseudonymize_address(customer.get("address", "")),
            "credit_limit": customer.get("credit_limit"),
            "current_exposure": customer.get("current_exposure"),
            "payment_terms": customer.get("payment_terms")
        }

        sales_rep = sales_order.get("sales_rep", {})
        result["sales_rep"] = {
            "name": self._pseudonymize_person_name(sales_rep.get("name", "")),
            "email": self._pseudonymize_email(sales_rep.get("email", ""))
        }

        order = sales_order.get("order", {})
        result["order"] = {
            "currency": order.get("currency"),
            "total_net": order.get("total_net"),
            "requested_delivery_date": order.get("requested_delivery_date"),
            "shipping_address": self._pseudonymize_address(order.get("shipping_address", "")),
            "discount_percent": order.get("discount_percent"),
            "historical_avg_discount_percent": order.get("historical_avg_discount_percent")
        }

        # Items
        items = sales_order.get("items", [])
        result["items"] = []
        for item in items:
            sku_token, desc_token = self._pseudonymize_product(
                item.get("sku", ""),
                item.get("description", "")
            )
            result["items"].append({
                "sku": sku_token,
                "description": desc_token,
                "quantity": item.get("quantity"),
                "unit_price": item.get("unit_price"),
                "unit_cost": item.get("unit_cost"),
                "margin_percent": item.get("margin_percent")
            })

        # Notes - use fallback regex patterns
        notes = sales_order.get("notes", "")
        result["notes"] = self._pseudonymize_text_fallback(notes)

        return result

    def depseudonymize_text(self, text: str) -> str:
        """Replace pseudonyms back with original data in analysis result."""
        result = text
        for token, original in self.reverse_mapping.items():
            if token in result:
                result = result.replace(token, original)
        return result

    def get_pseudonymization_summary(self) -> Dict[str, Any]:
        """Get summary of what was pseudonymized for logging."""
        detection_methods = self._get_detection_methods_used()

        return {
            "total_replacements": len(self.mapping),
            "categories": {
                category: count for category, count in self.counters.items() if count > 0
            },
            "sample_mappings": {
                token: original for token, original in list(self.reverse_mapping.items())[:5]
            },
            "detection_methods": detection_methods,
            "ner_enabled": self.use_ner,
            "ner_model": self.ner_detector.model_name if self.ner_detector else None,
            "tools_used": self._get_tools_used()
        }

    def _get_detection_methods_used(self) -> List[str]:
        """Get list of detection methods actually used during pseudonymization."""
        methods = []

        # Pure spaCy approach
        if hasattr(self, '_used_spacy_ner') and self._used_spacy_ner:
            methods.append("Automated AI/NLP Detection")

        # Fallback methods (only when spaCy not available)
        if hasattr(self, '_used_manual_patterns') and self._used_manual_patterns:
            methods.append("Manual field mapping (fallback)")

        if hasattr(self, '_used_regex_fallback') and self._used_regex_fallback:
            methods.append("Regex pattern matching (fallback)")

        return methods if methods else ["Manual field mapping (fallback)"]

    def _get_tools_used(self) -> Dict[str, Any]:
        """Get detailed information about tools used for detection."""
        if self.use_ner and self.ner_detector:
            # Pure spaCy approach
            model_info = self.ner_detector.get_model_info()
            return {
                "primary_method": "Automated AI/NLP Detection",
                "nlp_framework": f"spaCy {model_info.get('model_name', 'unknown')}",
                "language_model": f"{model_info.get('language', 'unknown')} language model",
                "entity_types": model_info.get('entities', []),
                "custom_patterns": list(self.ner_detector.custom_patterns.keys()),
                "automation_level": "Full automation - AI detects all sensitive data",
                "approach": "Pure NLP - no manual field mapping"
            }
        else:
            # Fallback to manual when spaCy not available
            return {
                "primary_method": "Manual field mapping",
                "nlp_framework": None,
                "language_model": None,
                "custom_patterns": [],
                "entity_types": [],
                "automation_level": "Manual patterns only",
                "approach": "Fallback mode - spaCy not available"
            }

    def pseudonymize_text_auto(self, text: str) -> str:
        """
        Automatically pseudonymize text using NER detection.

        Args:
            text: Input text to pseudonymize

        Returns:
            Pseudonymized text with detected entities replaced
        """
        if not self.use_ner or not self.ner_detector:
            return self._pseudonymize_text_fallback(text)

        self._used_spacy_ner = True

        entities = self.ner_detector.detect_entities(text)
        if not entities:
            return text

        # Reverse-sort by position so offsets stay valid as we replace
        entities.sort(key=lambda e: e.start, reverse=True)

        result = text
        for entity in entities:
            # Custom regex patterns also count as a detection method used
            if entity.label in self.ner_detector.custom_patterns:
                self._used_manual_patterns = True

            token_type = self._map_entity_to_token_type(entity.label)
            pseudonym = self._generate_token(token_type, entity.text)
            result = result[:entity.start] + pseudonym + result[entity.end:]

        return result

    def _map_entity_to_token_type(self, entity_label: str) -> str:
        """Map spaCy entity labels to our pseudonym token types."""
        label_mapping = {
            "PERSON": "person",
            "ORG": "organization",
            "GPE": "location",
            "LOC": "location",
            "MONEY": "financial",
            "DATE": "person",  # Dates might reveal personal info
            "EMAIL": "email",
            "PHONE": "phone",
            "FACILITY": "location",
            "ZIPCODE": "location",
            "IBAN": "financial",
            "SSN": "person",
            "CREDIT_CARD": "financial",
            "TAX_ID": "company"
        }
        return label_mapping.get(entity_label, "person")

    def _pseudonymize_text_fallback(self, text: str) -> str:
        """Fallback pseudonymization using regex patterns."""
        # Mark that we're using regex fallback
        self._used_regex_fallback = True

        result = text

        # Apply existing manual patterns
        patterns = [
            (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', "email"),
            (r'(?:\+\d{1,3}\s?)?(?:\d{1,4}[\s-]?){2,4}\d{1,4}', "phone"),
            (r'\b\d{3}-\d{2}-\d{4}\b', "person"),  # SSN
            (r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', "financial"),  # Credit card
        ]

        for pattern, token_type in patterns:
            for match in re.finditer(pattern, result):
                original = match.group()
                pseudonym = self._generate_token(token_type, original)
                result = result.replace(original, pseudonym)

        return result
