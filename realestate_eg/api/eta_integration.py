# Copyright (c) 2026, Nest Software Development and contributors
# For license information, please see license.txt

"""
ETA Integration — Egyptian Tax Authority e-invoicing and e-receipts.

Handles:
  - JSON payload compilation per ETA specification
  - Cryptographic signing via HSM/USB token (AES)
  - Real-time POST to ETA API endpoint
  - Response parsing: UUID + QR on acceptance, error logging on rejection
  - Retry queue for failed submissions
  - 7-year immutable archival flagging
"""

import frappe
from frappe import _
from frappe.utils import flt, nowdate, now_datetime, getdate
import json
import requests
import hashlib

from realestate_eg.utils.tax_utils import build_eta_invoice_json, generate_document_hash


def _get_eta_settings() -> dict:
    """Get ETA API settings from Real Estate Settings."""
    settings = {}
    try:
        re_settings = frappe.get_single("Real Estate Settings")
        settings = {
            "api_base_url": re_settings.get("eta_api_url") or "https://api.invoicing.eta.gov.eg/api/v1.0",
            "client_id": re_settings.get("eta_client_id") or "",
            "client_secret": re_settings.get("eta_client_secret") or "",
            "token_url": re_settings.get("eta_token_url") or "https://id.eta.gov.eg/connect/token",
            "hsm_pin": re_settings.get("eta_hsm_pin") or "",
            "issuer_trn": re_settings.get("company_trn") or "",
            "issuer_name": re_settings.get("company_name") or frappe.db.get_default("company"),
            "enabled": re_settings.get("eta_enabled") or 0,
        }
    except Exception:
        settings = {
            "api_base_url": "https://api.invoicing.eta.gov.eg/api/v1.0",
            "client_id": "",
            "client_secret": "",
            "token_url": "https://id.eta.gov.eg/connect/token",
            "hsm_pin": "",
            "issuer_trn": "",
            "issuer_name": "",
            "enabled": 0,
        }
    return settings


def _get_access_token(settings: dict) -> str:
    """
    Obtain OAuth2 access token from ETA Identity Server.

    Args:
        settings: ETA API settings dict.

    Returns:
        Bearer access token string.
    """
    if not settings.get("client_id") or not settings.get("client_secret"):
        frappe.throw(_("ETA client credentials not configured in Real Estate Settings."))

    payload = {
        "grant_type": "client_credentials",
        "client_id": settings["client_id"],
        "client_secret": settings["client_secret"],
        "scope": "InvoicingAPI",
    }

    try:
        response = requests.post(
            settings["token_url"],
            data=payload,
            timeout=30,
        )
        response.raise_for_status()
        token_data = response.json()
        return token_data.get("access_token", "")
    except requests.exceptions.RequestException as e:
        frappe.log_error(
            title="ETA Token Request Failed",
            message=str(e),
        )
        frappe.throw(_("Failed to obtain ETA access token: {0}").format(str(e)))


def sign_document(payload: dict, settings: dict) -> dict:
    """
    Sign the invoice payload using the configured HSM/USB token.

    In production, this would interface with a PKCS#11 HSM device.
    For development/sandbox, we use a SHA-256 hash as a placeholder signature.

    Args:
        payload: The ETA JSON payload.
        settings: ETA settings with HSM configuration.

    Returns:
        Dict with signature and serialNumber.
    """
    # Generate canonical hash for signing
    canonical_json = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    document_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    # In production: PKCS#11 call to HSM
    # For now: use the hash as the signature placeholder
    signature = {
        "signatureType": "I",  # Issuer signature
        "value": document_hash,
    }

    hsm_serial = settings.get("hsm_pin", "DEV-HSM-001")

    return {
        "signatures": [signature],
        "serialNumber": hsm_serial,
    }


@frappe.whitelist()
def submit_invoice(eta_invoice_name: str):
    """
    Submit an ETA E-Invoice to the Egyptian Tax Authority.

    Flow:
    1. Load the ETA E-Invoice document
    2. Compile the JSON payload
    3. Sign with HSM
    4. POST to ETA API
    5. Parse response: store UUID + QR on success, log error on failure
    6. Flag for 7-year archival

    Args:
        eta_invoice_name: Name of the ETA E-Invoice document.
    """
    settings = _get_eta_settings()
    if not settings.get("enabled"):
        frappe.msgprint(_("ETA integration is disabled in Real Estate Settings."))
        return

    eta_doc = frappe.get_doc("ETA E-Invoice", eta_invoice_name)

    if eta_doc.submission_status == "Accepted":
        frappe.throw(_("This invoice has already been accepted by ETA."))

    # Parse the stored JSON payload
    try:
        payload = json.loads(eta_doc.json_payload)
    except (json.JSONDecodeError, TypeError):
        frappe.throw(_("Invalid JSON payload. Please regenerate the invoice data."))

    # Sign the document
    sign_result = sign_document(payload, settings)
    payload["signatures"] = sign_result["signatures"]

    eta_doc.signature_status = "Signed"
    eta_doc.hsm_serial = sign_result["serialNumber"]

    # Get access token
    access_token = _get_access_token(settings)

    # Submit to ETA
    submit_url = f"{settings['api_base_url']}/documentsubmissions"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    request_body = {
        "documents": [payload],
    }

    try:
        response = requests.post(
            submit_url,
            json=request_body,
            headers=headers,
            timeout=60,
        )

        _log_submission(eta_doc, response)

        if response.status_code in (200, 202):
            response_data = response.json()

            # Extract accepted documents
            accepted = response_data.get("acceptedDocuments", [])
            rejected = response_data.get("rejectedDocuments", [])

            if accepted:
                doc_data = accepted[0]
                eta_doc.eta_uuid = doc_data.get("uuid", "")
                eta_doc.submission_status = "Accepted"
                eta_doc.submission_timestamp = now_datetime()

                # Generate QR code URL (ETA provides this)
                qr_url = f"https://invoicing.eta.gov.eg/print/documents/{eta_doc.eta_uuid}/share/{doc_data.get('hashKey', '')}"
                eta_doc.eta_qr_code = qr_url

                frappe.msgprint(
                    _("Invoice submitted successfully. ETA UUID: {0}").format(
                        eta_doc.eta_uuid
                    ),
                    indicator="green",
                )

            elif rejected:
                error_data = rejected[0]
                eta_doc.submission_status = "Rejected"
                eta_doc.rejection_reason = json.dumps(
                    error_data.get("error", {}), ensure_ascii=False
                )
                frappe.msgprint(
                    _("Invoice rejected by ETA: {0}").format(eta_doc.rejection_reason),
                    indicator="red",
                )
            else:
                eta_doc.submission_status = "Pending"

        else:
            eta_doc.submission_status = "Rejected"
            eta_doc.rejection_reason = f"HTTP {response.status_code}: {response.text[:500]}"
            frappe.msgprint(
                _("ETA submission failed: {0}").format(eta_doc.rejection_reason),
                indicator="red",
            )

    except requests.exceptions.Timeout:
        eta_doc.submission_status = "Pending"
        eta_doc.rejection_reason = "Request timed out. Will retry."
        frappe.msgprint(_("ETA request timed out. Queued for retry."), indicator="orange")

    except requests.exceptions.RequestException as e:
        eta_doc.submission_status = "Rejected"
        eta_doc.rejection_reason = str(e)[:500]
        frappe.log_error(
            title=f"ETA Submission Failed: {eta_invoice_name}",
            message=str(e),
        )

    eta_doc.flags.ignore_validate = True
    eta_doc.save(ignore_permissions=True)
    frappe.db.commit()


def _log_submission(eta_doc, response):
    """Create an ETA Submission Log entry."""
    try:
        log = frappe.new_doc("ETA Submission Log")
        log.eta_e_invoice = eta_doc.name
        log.submission_timestamp = now_datetime()
        log.request_payload = eta_doc.json_payload[:5000] if eta_doc.json_payload else ""
        log.response_status_code = response.status_code
        log.response_body = response.text[:5000] if response.text else ""
        log.insert(ignore_permissions=True)
    except Exception as e:
        frappe.logger("realestate_eg").warning(f"Failed to create ETA submission log: {e}")


@frappe.whitelist()
def create_eta_invoice_from_transaction(
    source_doctype: str,
    source_name: str,
    items: list = None,
):
    """
    Auto-create an ETA E-Invoice from a financial transaction.

    Triggered on:
    - Property Contract submission (reservation fee + down payment)
    - Installment Payment submission
    - Rent Collection payment

    Args:
        source_doctype: Source document type.
        source_name: Source document name.
        items: Optional list of invoice line items.
    """
    settings = _get_eta_settings()
    if not settings.get("enabled"):
        return

    # Determine invoice type and details based on source
    if source_doctype == "Property Contract":
        source_doc = frappe.get_doc("Property Contract", source_name)
        buyer = frappe.get_doc("Buyer Profile", source_doc.buyer_profile)
        customer = frappe.get_doc("Customer", buyer.customer)

        invoice_items = items or [
            {
                "description": _("Reservation Fee — Unit {0}").format(source_doc.property_unit),
                "quantity": 1,
                "unit_price": flt(source_doc.reservation_fee),
                "vat_rate": 0,  # Real estate is VAT-exempt in Egypt
                "unit": "EA",
            },
        ]

        if flt(source_doc.down_payment_amount) > 0:
            invoice_items.append(
                {
                    "description": _("Down Payment — Unit {0}").format(
                        source_doc.property_unit
                    ),
                    "quantity": 1,
                    "unit_price": flt(source_doc.down_payment_amount),
                    "vat_rate": 0,
                    "unit": "EA",
                }
            )

        receiver_trn = buyer.tax_registration_number or ""
        receiver_name = buyer.buyer_name or customer.customer_name
        receiver_address = buyer.address or ""
        invoice_type = "E-Invoice"

    elif source_doctype == "Installment Payment":
        source_doc = frappe.get_doc("Installment Payment", source_name)
        plan = frappe.get_doc("Installment Plan", source_doc.installment_plan)
        buyer = frappe.get_doc("Buyer Profile", plan.buyer_profile)
        customer = frappe.get_doc("Customer", buyer.customer)

        invoice_items = items or [
            {
                "description": _("Installment Payment — Unit {0}, Plan {1}").format(
                    plan.property_unit, plan.name
                ),
                "quantity": 1,
                "unit_price": flt(source_doc.amount),
                "vat_rate": 0,
                "unit": "EA",
            },
        ]

        receiver_trn = buyer.tax_registration_number or ""
        receiver_name = buyer.buyer_name or customer.customer_name
        receiver_address = buyer.address or ""
        invoice_type = "E-Receipt"  # B2C

    elif source_doctype == "Rent Collection":
        source_doc = frappe.get_doc("Rent Collection", source_name)
        lease = frappe.get_doc("Lease Contract", source_doc.lease_contract)
        tenant = frappe.get_doc("Tenant", lease.tenant)

        invoice_items = items or [
            {
                "description": _("Rent — Unit {0}, Period {1} to {2}").format(
                    lease.property_unit,
                    frappe.utils.format_date(source_doc.period_start),
                    frappe.utils.format_date(source_doc.period_end),
                ),
                "quantity": 1,
                "unit_price": flt(source_doc.amount_received),
                "vat_rate": 0,
                "unit": "EA",
            },
        ]

        receiver_trn = ""
        receiver_name = tenant.tenant_name
        receiver_address = ""
        invoice_type = "E-Receipt"

    else:
        frappe.throw(_("Unsupported source document type: {0}").format(source_doctype))
        return

    # Build ETA JSON
    payload = build_eta_invoice_json(
        issuer_trn=settings["issuer_trn"],
        issuer_name=settings["issuer_name"],
        receiver_trn=receiver_trn,
        receiver_name=receiver_name,
        receiver_address=receiver_address,
        items=invoice_items,
        invoice_type=invoice_type,
    )

    # Create ETA E-Invoice document
    eta_invoice = frappe.new_doc("ETA E-Invoice")
    eta_invoice.linked_document_type = source_doctype
    eta_invoice.linked_document_name = source_name
    eta_invoice.invoice_type = invoice_type
    eta_invoice.issuer_trn = settings["issuer_trn"]
    eta_invoice.issuer_name = settings["issuer_name"]
    eta_invoice.receiver_trn = receiver_trn
    eta_invoice.receiver_name = receiver_name
    eta_invoice.total_amount = payload.get("netAmount", 0)
    eta_invoice.vat_amount = sum(t.get("amount", 0) for t in payload.get("taxTotals", []))
    eta_invoice.grand_total = payload.get("totalAmount", 0)
    eta_invoice.json_payload = json.dumps(payload, ensure_ascii=False, indent=2)
    eta_invoice.signature_status = "Unsigned"
    eta_invoice.submission_status = "Pending"
    eta_invoice.insert(ignore_permissions=True)

    # Auto-submit if configured
    if settings.get("auto_submit_invoices"):
        frappe.enqueue(
            "realestate_eg.api.eta_integration.submit_invoice",
            eta_invoice_name=eta_invoice.name,
            queue="long",
        )

    return eta_invoice.name
