"""
AI Agent Demo Page
=================

Direct access to AI Agent Demo page without Frappe wrapper.
This creates a clean, standalone page that can be viewed directly.
"""

import frappe

def get_context(context):
    """
    Set up context for AI Agent Demo page.
    """
    context.update({
        'no_header': True,
        'no_footer': True,
        'no_breadcrumbs': True,
        'no_sidebar': True,
        'title': 'AI Agent Demo - TechParts',
        'show_in_website': 1,
        'page_name': 'ai-agent-demo'
    })

    return context