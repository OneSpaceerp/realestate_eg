# Copyright (c) 2026, Nest Software Development and contributors
# For license information, please see license.txt

"""
SMS Gateway — Vodafone Business / Cequens integration for notifications.
"""

import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime
import requests


def _get_sms_settings() -> dict:
    """Get SMS gateway settings from Real Estate Settings."""
    try:
        settings = frappe.get_single("Real Estate Settings")
        return {
            "enabled": settings.get("sms_gateway_enabled") or 0,
            "provider": settings.get("sms_provider") or "Cequens",
            "api_url": settings.get("sms_api_url") or "",
            "api_key": settings.get("sms_api_key") or "",
            "sender_id": settings.get("sms_sender_id") or "RealEstateEG",
        }
    except Exception:
        return {"enabled": 0}


@frappe.whitelist()
def send_sms(phone_number: str, message: str, sender_id: str = None) -> dict:
    """
    Send an SMS message via the configured gateway.

    Args:
        phone_number: Recipient phone number (Egyptian format +20...).
        message: Message content (max 160 chars for single SMS).
        sender_id: Optional sender ID override.

    Returns:
        Dict with status and message_id.
    """
    settings = _get_sms_settings()

    if not settings.get("enabled"):
        frappe.logger("realestate_eg").info(
            f"SMS disabled. Would have sent to {phone_number}: {message[:50]}..."
        )
        return {"status": "disabled", "message": "SMS gateway is disabled"}

    # Normalize phone number to Egyptian format
    phone = _normalize_phone(phone_number)

    provider = settings.get("provider", "Cequens")
    result = {"status": "failed", "message_id": None}

    try:
        if provider == "Cequens":
            result = _send_via_cequens(phone, message, settings, sender_id)
        elif provider == "Vodafone Business":
            result = _send_via_vodafone(phone, message, settings, sender_id)
        else:
            # Generic HTTP API
            result = _send_via_generic(phone, message, settings, sender_id)

    except Exception as e:
        frappe.log_error(
            title=f"SMS Send Failed: {phone_number}",
            message=str(e),
        )
        result = {"status": "error", "message": str(e)}

    # Log the SMS
    _log_sms(phone, message, result)

    return result


def _normalize_phone(phone: str) -> str:
    """Normalize phone number to international format."""
    phone = phone.strip().replace(" ", "").replace("-", "")
    if phone.startswith("0"):
        phone = "+20" + phone[1:]
    elif not phone.startswith("+"):
        phone = "+20" + phone
    return phone


def _send_via_cequens(phone: str, message: str, settings: dict, sender_id: str = None) -> dict:
    """Send SMS via Cequens API."""
    payload = {
        "senderName": sender_id or settings.get("sender_id", "RealEstateEG"),
        "messageType": "text",
        "acknowledgement": 1,
        "messageText": message,
        "recipients": phone,
    }

    headers = {
        "Authorization": f"Bearer {settings['api_key']}",
        "Content-Type": "application/json",
    }

    response = requests.post(
        settings.get("api_url", "https://apis.cequens.com/sms/v1/messages"),
        json=payload,
        headers=headers,
        timeout=30,
    )

    if response.status_code in (200, 201, 202):
        data = response.json()
        return {
            "status": "sent",
            "message_id": data.get("messageId", ""),
        }
    else:
        return {
            "status": "failed",
            "message": f"HTTP {response.status_code}: {response.text[:200]}",
        }


def _send_via_vodafone(phone: str, message: str, settings: dict, sender_id: str = None) -> dict:
    """Send SMS via Vodafone Business API."""
    payload = {
        "AccountId": settings.get("api_key", ""),
        "SenderName": sender_id or settings.get("sender_id", "RealEstateEG"),
        "ReceiverMSISDN": phone,
        "SMSText": message,
    }

    response = requests.post(
        settings.get("api_url", "https://e3len.vodafone.com.eg/web2sms/sms/submit"),
        json=payload,
        timeout=30,
    )

    if response.status_code == 200:
        return {"status": "sent", "message_id": ""}
    else:
        return {
            "status": "failed",
            "message": f"HTTP {response.status_code}: {response.text[:200]}",
        }


def _send_via_generic(phone: str, message: str, settings: dict, sender_id: str = None) -> dict:
    """Send SMS via a generic HTTP API."""
    payload = {
        "to": phone,
        "message": message,
        "sender_id": sender_id or settings.get("sender_id"),
        "api_key": settings.get("api_key"),
    }

    response = requests.post(
        settings.get("api_url"),
        json=payload,
        timeout=30,
    )

    if response.status_code in (200, 201, 202):
        return {"status": "sent", "message_id": ""}
    else:
        return {
            "status": "failed",
            "message": f"HTTP {response.status_code}",
        }


def _log_sms(phone: str, message: str, result: dict):
    """Log SMS send attempt for audit trail."""
    frappe.get_doc(
        {
            "doctype": "Comment",
            "comment_type": "Info",
            "reference_doctype": "Real Estate Settings",
            "reference_name": "Real Estate Settings",
            "content": f"SMS to {phone}: {result.get('status', 'unknown')} — {message[:100]}",
        }
    ).insert(ignore_permissions=True)
