"""Integration tests for global LLM settings permissions and secrets."""
from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from ...api import get_llm_settings
from ...core.llm_client import OLLAMA_NATIVE_FORMAT, PUBLIC_PROVIDER


class TestAIAgentLLMSettings(FrappeTestCase):
    """Verify that only safe configuration metadata reaches the browser."""

    def setUp(self) -> None:
        self.previous_user = frappe.session.user
        frappe.set_user("Administrator")

    def tearDown(self) -> None:
        frappe.set_user(self.previous_user)

    def test_guest_cannot_read_settings(self) -> None:
        frappe.set_user("Guest")

        with self.assertRaises(frappe.PermissionError):
            get_llm_settings()

    def test_serialized_settings_never_include_api_key(self) -> None:
        settings = frappe.get_single("AI Agent LLM Settings")
        settings.provider_type = PUBLIC_PROVIDER
        settings.public_api_format = OLLAMA_NATIVE_FORMAT
        settings.public_base_url = "https://ollama.com/api"
        settings.public_model = "_Test Public Model"
        settings.api_key = "_Test Secret Key"
        settings.save()

        result = get_llm_settings()

        self.assertTrue(result["api_key_set"])
        self.assertNotIn("api_key", result)
        self.assertNotIn("_Test Secret Key", str(result))
