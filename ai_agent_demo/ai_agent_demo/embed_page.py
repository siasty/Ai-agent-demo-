"""
Embed Page Handler
==================

Renders pages without Frappe desk interface for clean embedding.
"""

import frappe
from frappe import _
from frappe.website.serve import get_response


@frappe.whitelist(allow_guest=True)
def get_embed_page(page_name: str):
    """
    Render a specific page without Frappe desk interface.

    Args:
        page_name: Name of the page to render

    Returns:
        Clean HTML content suitable for embedding
    """
    if not page_name:
        return {"error": "Page name is required"}

    if not frappe.db.exists("Page", page_name):
        return {"error": f"Page '{page_name}' not found"}

    try:
        # Get the page document
        page_doc = frappe.get_doc("Page", page_name)

        # Check permissions
        if not page_doc.has_permission("read"):
            return {"error": "Access denied"}

        # Get page content
        page_content = get_page_content(page_doc)

        return {
            "success": True,
            "content": page_content,
            "title": page_doc.title or page_name
        }

    except Exception as e:
        frappe.log_error(f"Error rendering embed page {page_name}: {str(e)}")
        return {"error": "Failed to load page content"}


def get_page_content(page_doc):
    """
    Extract clean content from page document.
    """
    # Build the page content HTML
    content_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{page_doc.title or page_doc.name}</title>
        <link rel="stylesheet" href="/assets/frappe/css/frappe-web.css">
        <style>
            body {{
                margin: 0;
                padding: 20px;
                background: #f8f9fa;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }}
            .embed-container {{
                background: white;
                border-radius: 8px;
                padding: 30px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                max-width: 1200px;
                margin: 0 auto;
            }}
            .embed-header {{
                text-align: center;
                margin-bottom: 30px;
                padding-bottom: 20px;
                border-bottom: 1px solid #eee;
            }}
            .embed-header h1 {{
                margin: 0;
                color: #333;
                font-size: 28px;
                font-weight: 600;
            }}
            .embed-content {{
                line-height: 1.6;
            }}

            /* AI Agent Demo Specific Styles */
            .ai-demo-interface {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 40px;
                border-radius: 12px;
                text-align: center;
                margin: 20px 0;
            }}

            .ai-demo-interface h2 {{
                margin: 0 0 10px 0;
                font-size: 32px;
                font-weight: 700;
            }}

            .ai-demo-interface p {{
                margin: 0;
                font-size: 18px;
                opacity: 0.9;
            }}

            .demo-features {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin: 30px 0;
            }}

            .feature-card {{
                background: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 8px;
                padding: 20px;
                text-align: center;
            }}

            .feature-icon {{
                font-size: 48px;
                margin-bottom: 15px;
                display: block;
            }}

            .feature-card h3 {{
                margin: 0 0 10px 0;
                color: #495057;
            }}

            .feature-card p {{
                margin: 0;
                color: #6c757d;
                font-size: 14px;
            }}

            @media (max-width: 768px) {{
                body {{ padding: 10px; }}
                .embed-container {{ padding: 20px; }}
                .ai-demo-interface {{ padding: 20px; }}
                .ai-demo-interface h2 {{ font-size: 24px; }}
                .demo-features {{ grid-template-columns: 1fr; }}
            }}
        </style>
    </head>
    <body>
        <div class="embed-container">
            <div class="embed-header">
                <h1>{page_doc.title or page_doc.name}</h1>
            </div>
            <div class="embed-content">
                {get_page_specific_content(page_doc)}
            </div>
        </div>

        <script src="/assets/frappe/js/frappe-web.min.js"></script>
        <script>
            // Initialize any page-specific functionality
            document.addEventListener('DOMContentLoaded', function() {{
                console.log('Embed page loaded: {page_doc.name}');

                // Add any interactive elements here
                setupEmbedInteractions();
            }});

            function setupEmbedInteractions() {{
                // Add click handlers, form submissions, etc.
                const cards = document.querySelectorAll('.feature-card');
                cards.forEach(card => {{
                    card.addEventListener('click', function() {{
                        card.style.transform = 'scale(0.98)';
                        setTimeout(() => card.style.transform = 'scale(1)', 150);
                    }});
                }});
            }}
        </script>
    </body>
    </html>
    """

    return content_html


def get_page_specific_content(page_doc):
    """
    Generate specific content based on page type.
    """
    page_name = page_doc.name

    if page_name == "ai-agent-demo":
        return """
        <div class="ai-demo-interface">
            <h2>🤖 AI Agent Demo - TechParts Sp. z o.o.</h2>
            <p>Demonstracja agenta AI z automatyczną anonimizacją danych osobowych</p>
        </div>

        <div class="demo-features">
            <div class="feature-card">
                <span class="feature-icon">🛡️</span>
                <h3>Anonimizacja Danych</h3>
                <p>Automatyczna ochrona danych osobowych zgodnie z RODO</p>
            </div>
            <div class="feature-card">
                <span class="feature-icon">🧠</span>
                <h3>AI Processing</h3>
                <p>Zaawansowane przetwarzanie języka naturalnego</p>
            </div>
            <div class="feature-card">
                <span class="feature-icon">⚡</span>
                <h3>Lokalny Model</h3>
                <p>Przetwarzanie na lokalnej infrastrukturze TechParts</p>
            </div>
            <div class="feature-card">
                <span class="feature-icon">📊</span>
                <h3>Integracja ERP</h3>
                <p>Bezpośrednia integracja z systemem Frappe/ERPNext</p>
            </div>
        </div>

        <div style="text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee;">
            <p style="color: #6c757d; margin: 0;">
                <small>Demo Environment • TechParts Sp. z o.o. • 2026</small>
            </p>
        </div>
        """

    # Default content for other pages
    return f"""
    <div style="text-align: center; padding: 40px;">
        <h2>📄 {page_doc.title or page_doc.name}</h2>
        <p style="color: #6c757d;">This page is ready for embedding!</p>
        <p style="color: #6c757d; font-size: 14px;">
            To customize this content, edit the <code>get_page_specific_content()</code>
            function in <code>embed_page.py</code>
        </p>
    </div>
    """