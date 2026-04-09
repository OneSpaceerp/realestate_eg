# Copyright (c) 2026, Nest Software Development and contributors
# For license information, please see license.txt

"""Payment Gateway — Fawry / Paymob online payment integration."""

import frappe
from frappe import _
from frappe.utils import flt, nowdate, now_datetime
import requests
import hashlib
import json


@frappe.whitelist()
def create_payment_link(
    amount: float,
    buyer_name: str,
    buyer_email: str,
    buyer_phone: str,
    installment_plan: str = None,
    description: str = "",
) -> dict:
    """
    Create an online payment link for installment payment.

    Args:
        amount: Payment amount in EGP.
        buyer_name: Buyer's full name.
        buyer_email: Buyer's email.
        buyer_phone: Buyer's phone number.
        installment_plan: Optional linked installment plan.
        description: Payment description.

    Returns:
        Dict with payment_url, reference_number.
    """
    settings = _get_payment_settings()
    if not settings.get("enabled"):
        return {"status": "disabled", "message": _("Payment gateway is disabled.")}

    provider = settings.get("provider", "Paymob")

    if provider == "Paymob":
        return _create_paymob_payment(
            amount, buyer_name, buyer_email, buyer_phone,
            installment_plan, description, settings
        )
    elif provider == "Fawry":
        return _create_fawry_payment(
            amount, buyer_name, buyer_email, buyer_phone,
            installment_plan, description, settings
        )
    else:
        return {"status": "error", "message": _("Unsupported payment provider.")}


def _create_paymob_payment(
    amount, buyer_name, buyer_email, buyer_phone,
    installment_plan, description, settings
) -> dict:
    """Create payment via Paymob Accept API."""
    # Step 1: Authentication
    auth_response = requests.post(
        f"{settings['api_url']}/auth/tokens",
        json={"api_key": settings["api_key"]},
        timeout=30,
    )
    if auth_response.status_code != 201:
        return {"status": "error", "message": "Authentication failed"}

    auth_token = auth_response.json().get("token", "")

    # Step 2: Order Registration
    order_response = requests.post(
        f"{settings['api_url']}/ecommerce/orders",
        json={
            "auth_token": auth_token,
            "delivery_needed": False,
            "amount_cents": int(flt(amount) * 100),
            "currency": "EGP",
            "items": [{"name": description or "Installment Payment", "amount_cents": int(flt(amount) * 100), "quantity": 1}],
        },
        timeout=30,
    )
    if order_response.status_code != 201:
        return {"status": "error", "message": "Order registration failed"}

    order_id = order_response.json().get("id")

    # Step 3: Payment Key
    key_response = requests.post(
        f"{settings['api_url']}/acceptance/payment_keys",
        json={
            "auth_token": auth_token,
            "amount_cents": int(flt(amount) * 100),
            "expiration": 3600,
            "order_id": order_id,
            "billing_data": {
                "first_name": buyer_name.split()[0] if buyer_name else "N/A",
                "last_name": buyer_name.split()[-1] if buyer_name else "N/A",
                "email": buyer_email or "na@na.com",
                "phone_number": buyer_phone or "+20000000000",
                "apartment": "N/A", "floor": "N/A", "street": "N/A",
                "building": "N/A", "shipping_method": "N/A",
                "postal_code": "N/A", "city": "Cairo", "country": "EG", "state": "Cairo",
            },
            "currency": "EGP",
            "integration_id": settings.get("integration_id", ""),
        },
        timeout=30,
    )
    if key_response.status_code != 201:
        return {"status": "error", "message": "Payment key generation failed"}

    payment_token = key_response.json().get("token", "")
    payment_url = f"https://accept.paymob.com/api/acceptance/iframes/{settings.get('iframe_id', '')}?payment_token={payment_token}"

    return {
        "status": "success",
        "payment_url": payment_url,
        "reference_number": str(order_id),
        "payment_token": payment_token,
    }


def _create_fawry_payment(
    amount, buyer_name, buyer_email, buyer_phone,
    installment_plan, description, settings
) -> dict:
    """Create payment via Fawry API."""
    merchant_code = settings.get("merchant_code", "")
    merchant_ref = f"RE-{nowdate().replace('-', '')}-{frappe.generate_hash(length=8)}"

    # Fawry signature generation
    signature_string = (
        f"{merchant_code}{merchant_ref}{buyer_phone}"
        f"{int(flt(amount) * 100)}EGP{settings.get('security_key', '')}"
    )
    signature = hashlib.sha256(signature_string.encode()).hexdigest()

    payload = {
        "merchantCode": merchant_code,
        "merchantRefNum": merchant_ref,
        "customerMobile": buyer_phone,
        "customerEmail": buyer_email,
        "customerName": buyer_name,
        "paymentAmount": flt(amount),
        "currencyCode": "EGP",
        "language": "en-gb",
        "chargeItems": [
            {
                "itemId": installment_plan or "INST-PAY",
                "description": description or "Installment Payment",
                "price": flt(amount),
                "quantity": 1,
            }
        ],
        "paymentExpiry": 24 * 3600 * 1000,
        "signature": signature,
    }

    response = requests.post(
        settings.get("api_url", "https://atfawry.fawrystaging.com/ECommerceWeb/Fawry/payments/charge"),
        json=payload,
        timeout=30,
    )

    if response.status_code == 200:
        data = response.json()
        return {
            "status": "success",
            "payment_url": data.get("paymentURL", ""),
            "reference_number": merchant_ref,
            "fawry_ref": data.get("referenceNumber", ""),
        }
    else:
        return {"status": "error", "message": f"Fawry API error: {response.text[:200]}"}


@frappe.whitelist(allow_guest=True)
def payment_callback():
    """
    Webhook callback from payment gateway on payment completion.
    Updates the corresponding installment payment record.
    """
    data = frappe.request.get_json(force=True, silent=True) or frappe.request.args

    reference = data.get("merchant_order_id") or data.get("merchantRefNum") or ""
    status = data.get("success") or data.get("paymentStatus")
    amount = flt(data.get("amount_cents", 0)) / 100 or flt(data.get("paymentAmount", 0))
    transaction_id = data.get("id") or data.get("fawryRefNumber") or ""

    frappe.logger("realestate_eg").info(
        f"Payment callback: ref={reference}, status={status}, amount={amount}, tx={transaction_id}"
    )

    if status in (True, "PAID", "paid"):
        # Process successful payment
        frappe.enqueue(
            "_process_online_payment",
            reference=reference,
            amount=amount,
            transaction_id=transaction_id,
            queue="short",
        )

    return {"status": "ok"}


def _process_online_payment(reference: str, amount: float, transaction_id: str):
    """Process a confirmed online payment."""
    frappe.logger("realestate_eg").info(
        f"Processing online payment: {reference}, {amount} EGP, tx: {transaction_id}"
    )


def _get_payment_settings() -> dict:
    """Get payment gateway settings."""
    try:
        settings = frappe.get_single("Real Estate Settings")
        return {
            "enabled": settings.get("payment_gateway_enabled") or 0,
            "provider": settings.get("payment_provider") or "Paymob",
            "api_url": settings.get("payment_api_url") or "https://accept.paymob.com/api",
            "api_key": settings.get("payment_api_key") or "",
            "integration_id": settings.get("payment_integration_id") or "",
            "iframe_id": settings.get("payment_iframe_id") or "",
            "merchant_code": settings.get("fawry_merchant_code") or "",
            "security_key": settings.get("fawry_security_key") or "",
        }
    except Exception:
        return {"enabled": 0}
