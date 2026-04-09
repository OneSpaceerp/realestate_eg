# Copyright (c) 2026, Nest Software Development and contributors
# For license information, please see license.txt

"""WhatsApp Business Cloud API integration for customer notifications."""

import frappe
from frappe import _
from frappe.utils import flt
import requests
import json


@frappe.whitelist()
def send_whatsapp_message(
    phone_number: str,
    template_name: str,
    template_params: list = None,
    language_code: str = "ar",
) -> dict:
    """
    Send a WhatsApp message using a pre-approved template.

    Args:
        phone_number: Recipient phone in international format (+20...).
        template_name: Approved WhatsApp template name.
        template_params: List of parameter values for the template.
        language_code: Template language (ar for Arabic, en for English).

    Returns:
        Dict with status and message_id.
    """
    settings = _get_whatsapp_settings()
    if not settings.get("enabled"):
        return {"status": "disabled"}

    phone = phone_number.replace("+", "").replace(" ", "").replace("-", "")

    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
        },
    }

    if template_params:
        components = [
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": str(p)} for p in template_params
                ],
            }
        ]
        payload["template"]["components"] = components

    headers = {
        "Authorization": f"Bearer {settings['access_token']}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            f"https://graph.facebook.com/v18.0/{settings['phone_number_id']}/messages",
            json=payload,
            headers=headers,
            timeout=30,
        )

        if response.status_code in (200, 201):
            data = response.json()
            msg_id = data.get("messages", [{}])[0].get("id", "")
            return {"status": "sent", "message_id": msg_id}
        else:
            return {
                "status": "failed",
                "message": f"HTTP {response.status_code}: {response.text[:200]}",
            }

    except Exception as e:
        frappe.log_error(title="WhatsApp Send Failed", message=str(e))
        return {"status": "error", "message": str(e)}


def _get_whatsapp_settings() -> dict:
    """Get WhatsApp settings."""
    try:
        settings = frappe.get_single("Real Estate Settings")
        return {
            "enabled": settings.get("whatsapp_enabled") or 0,
            "access_token": settings.get("whatsapp_access_token") or "",
            "phone_number_id": settings.get("whatsapp_phone_number_id") or "",
        }
    except Exception:
        return {"enabled": 0}
