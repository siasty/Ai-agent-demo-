"""
Web handler for embed pages
"""

import frappe
from ai_agent_demo.ai_agent_demo.embed_page import get_embed_page


def get_context(context):
    """Handle embed page requests"""
    page_name = frappe.form_dict.get('page_name') or context.get('page_name')

    if not page_name:
        frappe.throw("Page name is required", frappe.DoesNotExistError)

    # Get embed page content
    result = get_embed_page(page_name)

    if result.get('error'):
        frappe.throw(result['error'], frappe.DoesNotExistError)

    # Set context for template
    context.update({
        'page_content': result.get('content', ''),
        'page_title': result.get('title', page_name),
        'no_header': True,
        'no_footer': True,
        'no_sidebar': True
    })

    return context