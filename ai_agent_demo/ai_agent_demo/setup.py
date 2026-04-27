"""
Setup functions for AI Agent Demo workspace and custom blocks.
Following agencik_app pattern for proper Frappe workspace implementation.
"""
from __future__ import annotations

import json
from contextlib import contextmanager

import frappe

# Constants for AI Agent Demo integration
AI_AGENT_ACCESS_ROLES = ("System Manager", "Workspace Manager")

# Custom CSS for AI Agent Demo embed
AI_AGENT_CUSTOM_BLOCK_STYLE = """
.ai-agent-demo-root {
    margin: 0;
    padding: 0;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.ai-agent-header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 24px;
    text-align: center;
}

.ai-agent-header h2 {
    margin: 0 0 8px 0;
    font-size: 24px;
    font-weight: 600;
}

.ai-agent-header p {
    margin: 0;
    opacity: 0.9;
    font-size: 16px;
}

.page-embed-iframe {
    border: none;
    background: #f8f9fa;
}

@media (max-width: 768px) {
    .ai-agent-header {
        padding: 16px;
    }

    .ai-agent-header h2 {
        font-size: 20px;
    }

    .ai-agent-header p {
        font-size: 14px;
    }
}
""".strip()


def after_migrate():
    """Called after every migration to ensure AI Agent Demo integration."""
    # Integration with workspace_page_embedder module
    _setup_ai_agent_page_embeds()
    frappe.clear_cache()


def _setup_ai_agent_page_embeds():
    """Setup AI Agent Demo page embeds using the workspace_page_embedder system."""
    # Check if workspace_page_embedder is available
    if not frappe.db.table_exists("Page Embed"):
        frappe.msgprint("Workspace Page Embedder module not found. Please install it first.", "Warning")
        return

    # Create a page embed for AI Agent Demo interface
    embed_name = "AI Agent Demo Interface"

    if not frappe.db.exists("Page Embed", embed_name):
        # Create the page embed document
        embed_doc = frappe.get_doc({
            "doctype": "Page Embed",
            "embed_name": embed_name,
            "target_page": "ai-agent-demo",  # This should be your custom page
            "description": "AI Agent Demo interface with data anonymization",
            "enabled": 1,
            "display_height": 700,
            "display_width": 100,
            "responsive": 1,
            "loading_message": "Loading AI Agent Demo...",
            "error_message": "AI Agent Demo temporarily unavailable. Please contact administrator.",
            "custom_css": AI_AGENT_CUSTOM_BLOCK_STYLE,
            "permissions": [
                {"role": "System Manager", "read": 1},
                {"role": "Workspace Manager", "read": 1}
            ]
        })

        try:
            embed_doc.insert(ignore_permissions=True)
            frappe.msgprint(f"✅ Created Page Embed: {embed_name}")
        except Exception as e:
            frappe.log_error(f"Failed to create Page Embed: {str(e)}")

    # Ensure we have the required roles
    for role in AI_AGENT_ACCESS_ROLES:
        if not frappe.db.exists("Role", role):
            role_doc = frappe.get_doc({
                "doctype": "Role",
                "role_name": role,
                "desk_access": 1
            })
            role_doc.insert(ignore_if_duplicate=True)