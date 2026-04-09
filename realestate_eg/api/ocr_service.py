# Copyright (c) 2026, Nest Software Development and contributors
# For license information, please see license.txt

"""
OCR Service — Cheque image scanning and data extraction.
"""

import frappe
from frappe import _
from frappe.utils import flt
import requests
import json


@frappe.whitelist()
def scan_cheque(image_url: str, pdc_name: str = None) -> dict:
    """
    Send a cheque image to the OCR service for data extraction.

    Args:
        image_url: URL or file path of the cheque image.
        pdc_name: Optional PDC document to verify against.

    Returns:
        Dict with extracted fields: cheque_number, amount, drawee_bank, drawer_name, date.
    """
    settings = _get_ocr_settings()

    if not settings.get("enabled"):
        frappe.msgprint(_("OCR service is disabled. Please configure in Real Estate Settings."))
        return {"status": "disabled"}

    try:
        # Download image if it's a Frappe file URL
        if image_url.startswith("/"):
            file_doc = frappe.get_doc("File", {"file_url": image_url})
            image_data = file_doc.get_content()
        else:
            resp = requests.get(image_url, timeout=30)
            image_data = resp.content

        # Send to OCR API
        ocr_response = requests.post(
            settings["api_url"],
            files={"image": ("cheque.jpg", image_data, "image/jpeg")},
            headers={"Authorization": f"Bearer {settings['api_key']}"},
            timeout=60,
        )

        if ocr_response.status_code != 200:
            return {
                "status": "error",
                "message": f"OCR API returned {ocr_response.status_code}",
            }

        extracted = ocr_response.json()

        result = {
            "status": "success",
            "cheque_number": extracted.get("cheque_number", ""),
            "amount": flt(extracted.get("amount", 0)),
            "drawee_bank": extracted.get("bank_name", ""),
            "drawer_name": extracted.get("drawer_name", ""),
            "date": extracted.get("date", ""),
            "micr_code": extracted.get("micr", ""),
        }

        # If PDC provided, verify against system data
        if pdc_name:
            result["verification"] = _verify_against_pdc(pdc_name, result)

        return result

    except requests.exceptions.RequestException as e:
        frappe.log_error(title="OCR Scan Failed", message=str(e))
        return {"status": "error", "message": str(e)}


def _verify_against_pdc(pdc_name: str, ocr_data: dict) -> dict:
    """Compare OCR extracted data against stored PDC data."""
    pdc = frappe.get_doc("Post Dated Cheque", pdc_name)

    discrepancies = []
    is_verified = True

    if ocr_data.get("cheque_number") and ocr_data["cheque_number"] != pdc.cheque_number:
        discrepancies.append(
            f"Cheque number: OCR={ocr_data['cheque_number']}, System={pdc.cheque_number}"
        )
        is_verified = False

    if ocr_data.get("amount") and abs(flt(ocr_data["amount"]) - flt(pdc.amount)) > 0.01:
        discrepancies.append(
            f"Amount: OCR={ocr_data['amount']}, System={pdc.amount}"
        )
        is_verified = False

    if ocr_data.get("drawee_bank") and ocr_data["drawee_bank"].lower() != (pdc.drawee_bank or "").lower():
        discrepancies.append(
            f"Bank: OCR={ocr_data['drawee_bank']}, System={pdc.drawee_bank}"
        )
        is_verified = False

    # Update PDC with verification results
    frappe.db.set_value(
        "Post Dated Cheque",
        pdc_name,
        {
            "ocr_verified": 1 if is_verified else 0,
            "ocr_discrepancy_notes": "\n".join(discrepancies) if discrepancies else "",
        },
    )

    return {
        "is_verified": is_verified,
        "discrepancies": discrepancies,
    }


def _get_ocr_settings() -> dict:
    """Get OCR service settings."""
    try:
        settings = frappe.get_single("Real Estate Settings")
        return {
            "enabled": settings.get("ocr_enabled") or 0,
            "api_url": settings.get("ocr_api_url") or "",
            "api_key": settings.get("ocr_api_key") or "",
        }
    except Exception:
        return {"enabled": 0}
