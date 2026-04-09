# Copyright (c) 2026, Nest Software Development and contributors
# For license information, please see license.txt

"""
Tax Utilities — Transfer tax, property tax, and ETA e-invoice JSON builder.

Egyptian tax rules:
  - Land transfer tax: 2.5% of acquisition cost
  - Property tax: Based on annual assessed rental value
  - ETA e-invoice: JSON format per official ETA API specification
  - 7-year mandatory archival for all ETA documents
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate, now_datetime, cint
import json
import hashlib
import uuid


# Transfer tax rate
TRANSFER_TAX_RATE = 0.025  # 2.5%


def calculate_transfer_tax(acquisition_cost: float) -> float:
    """
    Calculate land transfer tax.

    Formula: acquisition_cost × 2.5%

    Args:
        acquisition_cost: Total land acquisition cost.

    Returns:
        Transfer tax amount.
    """
    return flt(flt(acquisition_cost) * TRANSFER_TAX_RATE, 2)


def build_eta_invoice_json(
    issuer_trn: str,
    issuer_name: str,
    receiver_trn: str,
    receiver_name: str,
    receiver_address: str,
    items: list[dict],
    invoice_type: str = "E-Invoice",
    currency: str = "EGP",
    document_type: str = "I",  # I = Invoice, C = Credit Note, D = Debit Note
) -> dict:
    """
    Build an ETA-compliant e-invoice JSON payload.

    ETA JSON structure per official specification:
    {
        "issuer": {...},
        "receiver": {...},
        "documentType": "I",
        "dateTimeIssued": "...",
        "taxpayerActivityCode": "...",
        "internalID": "...",
        "invoiceLines": [{...}],
        "totalSalesAmount": ...,
        "totalDiscountAmount": ...,
        "netAmount": ...,
        "totalAmount": ...
    }

    Args:
        issuer_trn: Developer's Tax Registration Number.
        issuer_name: Developer/company name.
        receiver_trn: Buyer's TRN (mandatory for B2B).
        receiver_name: Buyer/tenant name.
        receiver_address: Buyer address.
        items: List of line items with: description, quantity, unit, unit_price, vat_rate.
        invoice_type: E-Invoice or E-Receipt.
        currency: Default EGP.
        document_type: I (Invoice), C (Credit Note), D (Debit Note).

    Returns:
        Complete ETA-formatted JSON dict.
    """
    # Build issuer block
    issuer = {
        "type": "B",  # Business
        "id": issuer_trn,
        "name": issuer_name,
        "address": {
            "branchID": "0",
            "country": "EG",
            "governate": "",
            "regionCity": "",
            "street": "",
            "buildingNumber": "",
        },
    }

    # Build receiver block
    receiver = {
        "type": "B" if receiver_trn else "P",  # B = Business, P = Person
        "id": receiver_trn or "",
        "name": receiver_name,
        "address": {
            "country": "EG",
            "governate": "",
            "regionCity": "",
            "street": receiver_address or "",
            "buildingNumber": "",
        },
    }

    # Build invoice lines
    invoice_lines = []
    total_sales = 0.0
    total_discount = 0.0
    total_vat = 0.0

    for idx, item in enumerate(items, 1):
        quantity = flt(item.get("quantity", 1))
        unit_price = flt(item.get("unit_price", 0))
        discount = flt(item.get("discount", 0))
        vat_rate = flt(item.get("vat_rate", 14))  # Default 14% VAT in Egypt

        sales_amount = flt(quantity * unit_price, 5)
        net_amount = flt(sales_amount - discount, 5)
        vat_amount = flt(net_amount * vat_rate / 100, 5)
        total_amount = flt(net_amount + vat_amount, 5)

        total_sales += sales_amount
        total_discount += discount
        total_vat += vat_amount

        line = {
            "description": item.get("description", ""),
            "itemType": item.get("item_type", "GS1"),  # GS1 or EGS
            "itemCode": item.get("item_code", ""),
            "unitType": item.get("unit", "EA"),  # EA = Each
            "quantity": quantity,
            "internalCode": str(idx),
            "salesTotal": round(sales_amount, 5),
            "total": round(total_amount, 5),
            "valueDifference": 0,
            "totalTaxableFees": 0,
            "netTotal": round(net_amount, 5),
            "itemsDiscount": round(discount, 5),
            "unitValue": {
                "currencySold": currency,
                "amountEGP": round(unit_price, 5),
            },
            "discount": {
                "rate": round(discount / sales_amount * 100, 2) if sales_amount else 0,
                "amount": round(discount, 5),
            },
            "taxableItems": [
                {
                    "taxType": "T1",  # VAT
                    "amount": round(vat_amount, 5),
                    "subType": "V009" if vat_rate == 14 else "V001",
                    "rate": vat_rate,
                }
            ],
        }
        invoice_lines.append(line)

    net_total = flt(total_sales - total_discount, 5)

    payload = {
        "issuer": issuer,
        "receiver": receiver,
        "documentType": document_type,
        "documentTypeVersion": "1.0",
        "dateTimeIssued": now_datetime().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "taxpayerActivityCode": "6810",  # Real estate activities
        "internalID": str(uuid.uuid4())[:20],
        "purchaseOrderReference": "",
        "purchaseOrderDescription": "",
        "salesOrderReference": "",
        "salesOrderDescription": "",
        "proformaInvoiceNumber": "",
        "payment": {
            "bankName": "",
            "bankAddress": "",
            "bankAccountNo": "",
            "bankAccountIBAN": "",
            "swiftCode": "",
            "terms": "",
        },
        "delivery": {
            "approach": "",
            "packaging": "",
            "dateValidity": "",
            "exportPort": "",
            "grossWeight": 0,
            "netWeight": 0,
            "terms": "",
        },
        "invoiceLines": invoice_lines,
        "totalDiscountAmount": round(total_discount, 5),
        "totalSalesAmount": round(total_sales, 5),
        "netAmount": round(net_total, 5),
        "taxTotals": [
            {
                "taxType": "T1",
                "amount": round(total_vat, 5),
            }
        ],
        "totalAmount": round(net_total + total_vat, 5),
        "extraDiscountAmount": 0,
        "totalItemsDiscountAmount": round(total_discount, 5),
    }

    return payload


def generate_document_hash(payload: dict) -> str:
    """
    Generate a SHA-256 hash of the invoice payload for integrity verification.

    Args:
        payload: The ETA JSON payload dict.

    Returns:
        Hex digest string.
    """
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def format_egp_currency(amount, with_symbol=True) -> str:
    """
    Jinja method: Format amount as EGP currency string.

    Args:
        amount: Numeric amount.
        with_symbol: Whether to include 'EGP' prefix.

    Returns:
        Formatted string e.g., "EGP 1,250,000.00"
    """
    formatted = "{:,.2f}".format(flt(amount))
    if with_symbol:
        return f"EGP {formatted}"
    return formatted


def get_eta_qr_code(eta_uuid: str = None, invoice_name: str = None) -> str:
    """
    Jinja method: Get the QR code image URL for an ETA e-invoice.

    Args:
        eta_uuid: The 64-character UUID from ETA.
        invoice_name: Name of the ETA E-Invoice document.

    Returns:
        URL to the QR code image, or empty string if not available.
    """
    if invoice_name:
        qr = frappe.db.get_value("ETA E-Invoice", invoice_name, "eta_qr_code")
        return qr or ""
    return ""


def should_archive_eta_document(submission_date: str) -> bool:
    """
    Check if an ETA document should be marked for archival.
    Per Egyptian law, ETA documents must be archived for 7 years.

    Args:
        submission_date: Date the document was submitted.

    Returns:
        True if the document has been stored for 7+ years.
    """
    if not submission_date:
        return False
    submission = getdate(submission_date)
    today = getdate(nowdate())
    years_stored = (today - submission).days / 365.25
    return years_stored >= 7
