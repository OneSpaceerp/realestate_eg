# Copyright (c) 2026, Nest Software Development and contributors
# For license information, please see license.txt

"""Digital Signature — Contract e-signing integration (DocuSign / local providers)."""

import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime
import requests
import json


@frappe.whitelist()
def create_signing_request(
    contract_name: str,
    signer_name: str,
    signer_email: str,
) -> dict:
    """
    Create a digital signature request for a property contract.

    Args:
        contract_name: Property Contract document name.
        signer_name: Name of the person signing.
        signer_email: Email to send the signing request to.

    Returns:
        Dict with signing_url and envelope_id.
    """
    settings = _get_signature_settings()
    if not settings.get("enabled"):
        return {"status": "disabled", "message": _("Digital signature is disabled.")}

    contract = frappe.get_doc("Property Contract", contract_name)

    # Generate PDF of the contract for signing
    pdf_content = frappe.get_print(
        "Property Contract", contract_name, print_format="Standard", as_pdf=True
    )

    try:
        if settings.get("provider") == "DocuSign":
            return _create_docusign_envelope(
                contract, pdf_content, signer_name, signer_email, settings
            )
        else:
            return _create_generic_signing(
                contract, pdf_content, signer_name, signer_email, settings
            )
    except Exception as e:
        frappe.log_error(title="Digital Signature Failed", message=str(e))
        return {"status": "error", "message": str(e)}


def _create_docusign_envelope(contract, pdf_content, signer_name, signer_email, settings) -> dict:
    """Create a DocuSign envelope."""
    import base64

    document_base64 = base64.b64encode(pdf_content).decode("utf-8")

    envelope = {
        "emailSubject": f"Property Contract {contract.contract_number} — Please Sign",
        "documents": [
            {
                "documentBase64": document_base64,
                "name": f"Contract_{contract.contract_number}.pdf",
                "fileExtension": "pdf",
                "documentId": "1",
            }
        ],
        "recipients": {
            "signers": [
                {
                    "email": signer_email,
                    "name": signer_name,
                    "recipientId": "1",
                    "routingOrder": "1",
                    "tabs": {
                        "signHereTabs": [
                            {"documentId": "1", "pageNumber": "1", "xPosition": "100", "yPosition": "700"}
                        ]
                    },
                }
            ]
        },
        "status": "sent",
    }

    headers = {
        "Authorization": f"Bearer {settings['access_token']}",
        "Content-Type": "application/json",
    }

    response = requests.post(
        f"{settings['api_url']}/envelopes",
        json=envelope,
        headers=headers,
        timeout=60,
    )

    if response.status_code in (200, 201):
        data = response.json()
        envelope_id = data.get("envelopeId", "")

        frappe.db.set_value(
            "Property Contract",
            contract.name,
            {
                "digital_signature_status": "Pending",
                "digital_signature_url": f"Envelope: {envelope_id}",
            },
        )

        return {
            "status": "success",
            "envelope_id": envelope_id,
            "signing_url": data.get("uri", ""),
        }
    else:
        return {"status": "error", "message": f"DocuSign: {response.text[:200]}"}


def _create_generic_signing(contract, pdf_content, signer_name, signer_email, settings) -> dict:
    """Create a signing request using a generic e-signature API."""
    payload = {
        "document_name": f"Contract_{contract.contract_number}",
        "signer_email": signer_email,
        "signer_name": signer_name,
        "callback_url": f"{frappe.utils.get_url()}/api/method/realestate_eg.api.digital_signature.signing_callback",
    }

    response = requests.post(
        settings.get("api_url", ""),
        json=payload,
        headers={"Authorization": f"Bearer {settings.get('api_key', '')}"},
        timeout=60,
    )

    if response.status_code in (200, 201):
        data = response.json()
        return {
            "status": "success",
            "signing_url": data.get("signing_url", ""),
            "request_id": data.get("request_id", ""),
        }
    return {"status": "error", "message": f"HTTP {response.status_code}"}


@frappe.whitelist(allow_guest=True)
def signing_callback():
    """Webhook callback when signing is completed."""
    data = frappe.request.get_json(force=True, silent=True) or {}
    contract_ref = data.get("document_name", "")
    status = data.get("status", "")

    if status in ("completed", "signed"):
        contract_name = frappe.db.get_value(
            "Property Contract",
            {"contract_number": contract_ref.replace("Contract_", "")},
        )
        if contract_name:
            frappe.db.set_value(
                "Property Contract",
                contract_name,
                "digital_signature_status",
                "Fully Executed",
            )
            frappe.db.commit()

    return {"status": "ok"}


def _get_signature_settings() -> dict:
    """Get digital signature settings."""
    try:
        settings = frappe.get_single("Real Estate Settings")
        return {
            "enabled": settings.get("digital_signature_enabled") or 0,
            "provider": settings.get("signature_provider") or "DocuSign",
            "api_url": settings.get("signature_api_url") or "",
            "access_token": settings.get("signature_access_token") or "",
            "api_key": settings.get("signature_api_key") or "",
        }
    except Exception:
        return {"enabled": 0}
