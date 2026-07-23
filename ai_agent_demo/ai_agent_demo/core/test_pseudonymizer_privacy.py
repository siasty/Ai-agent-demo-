"""Privacy regression tests for ERP identifiers in LLM payloads."""
from __future__ import annotations

import json

from frappe.tests.utils import FrappeTestCase

from .pseudonymizer import BusinessPseudonymizer


class TestPseudonymizerPrivacy(FrappeTestCase):
    """Ensure document IDs are local-only even with a public provider."""

    def test_credit_payload_replaces_order_and_invoice_ids(self) -> None:
        pseudonymizer = BusinessPseudonymizer(use_ner=False)
        raw_data = {
            "currency": "PLN",
            "customer": {
                "name": "_Test Customer",
                "tax_id": "_Test Tax ID",
                "email": "test@example.com",
                "phone": "+48 123 456 789",
                "address": "_Test Street 1",
                "credit_limit": 1000,
                "customer_group": "Commercial",
                "territory": "All Territories",
            },
            "payment_history": {"has_payment_history": True},
            "recent_orders": [
                {
                    "sales_order_id": "SAL-ORD-2026-00006",
                    "sales_rep": "_Test Sales Person",
                }
            ],
            "outstanding_invoices": [
                {"invoice_id": "ACC-SINV-2026-00022"}
            ],
        }

        safe_data = pseudonymizer.pseudonymize_customer_data(raw_data)
        serialized = json.dumps(safe_data)

        self.assertEqual(
            safe_data["recent_orders"][0]["sales_order_id"],
            "SALES_ORDER_01",
        )
        self.assertEqual(
            safe_data["outstanding_invoices"][0]["invoice_id"],
            "INVOICE_01",
        )
        self.assertNotIn("SAL-ORD-2026-00006", serialized)
        self.assertNotIn("ACC-SINV-2026-00022", serialized)

    def test_sales_order_payload_replaces_primary_order_id(self) -> None:
        pseudonymizer = BusinessPseudonymizer(use_ner=False)
        raw_data = {
            "sales_order_id": "SAL-ORD-2026-00005",
            "customer": {},
            "sales_rep": {},
            "order": {},
            "items": [],
            "notes": "",
        }

        safe_data = pseudonymizer.pseudonymize_sales_order(raw_data)

        self.assertEqual(safe_data["sales_order_id"], "SALES_ORDER_01")
        self.assertNotIn("SAL-ORD-2026-00005", json.dumps(safe_data))
