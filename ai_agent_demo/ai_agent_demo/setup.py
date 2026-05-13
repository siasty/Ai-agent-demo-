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
    # Create workspace for AI Agent Demo
    _setup_ai_agent_workspace()
    frappe.clear_cache()


def _setup_ai_agent_workspace():
    """Setup AI Agent Demo workspace with proper page integration."""
    workspace_name = "AI Agent Demo - TechParts"

    if frappe.db.exists("Workspace", workspace_name):
        return  # Already exists

    # Create workspace
    workspace_doc = frappe.get_doc({
        "doctype": "Workspace",
        "name": workspace_name,
        "title": workspace_name,
        "icon": "robot",
        "module": "AI Agent Demo",
        "app": "ai_agent_demo",
        "is_standard": 0,
        "public": 1,
        "content": frappe.as_json([
            {
                "id": frappe.generate_hash(length=8),
                "type": "header",
                "data": {
                    "text": "🤖 AI Agent Demo",
                    "col": 12
                }
            },
            {
                "id": frappe.generate_hash(length=8),
                "type": "paragraph",
                "data": {
                    "text": "AI Agent demonstration with automatic personal data anonymization according to GDPR.",
                    "col": 12
                }
            },
            {
                "id": frappe.generate_hash(length=8),
                "type": "page",
                "data": {
                    "page_name": "ai-agent-demo",
                    "label": "🤖 Chat with AI Agent",
                    "col": 12
                }
            }
        ])
    })

    try:
        workspace_doc.insert(ignore_permissions=True)
        frappe.msgprint(f"✅ Created Workspace: {workspace_name}")
    except Exception as e:
        frappe.log_error(f"Failed to create workspace: {str(e)}")