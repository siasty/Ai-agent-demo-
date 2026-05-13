from frappe import _


def get_data():
    return [
        {
            "module_name": "AI Agent",
            "color": "#4361ee",
            "icon": "octicon octicon-hubot",
            "type": "module",
            "label": _("AI Agent Demo"),
            "description": _("AI agent demo – tool selection and data anonymization"),
        }
    ]
