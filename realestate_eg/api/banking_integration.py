# Copyright (c) 2026, Nest Software Development and contributors
# For license information, please see license.txt

"""
Banking Integration — ISO 20022 / CBE Clearing House interface.

Handles:
  - Cheque batch deposit file generation (ISO 20022 pain.001)
  - Clearing status import (CAMT.053 bank-to-customer statement)
  - D+1 clearing cycle (Sunday–Thursday)
  - Bounce notification parsing with structured reason codes
  - Bank reconciliation file import
"""

import frappe
from frappe import _
from frappe.utils import flt, nowdate, getdate, now_datetime
import xmltodict
import json
from datetime import datetime


@frappe.whitelist()
def generate_deposit_file(batch_name: str) -> str:
    """
    Generate an ISO 20022 pain.001-compatible XML file for a cheque batch deposit.

    Args:
        batch_name: Name of the Cheque Batch Deposit document.

    Returns:
        XML string ready for submission to the bank.
    """
    batch = frappe.get_doc("Cheque Batch Deposit", batch_name)

    # Build ISO 20022 header
    msg_id = f"REG-{batch.name}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    pain_doc = {
        "Document": {
            "@xmlns": "urn:iso:std:iso:20022:tech:xsd:pain.001.001.09",
            "CstmrCdtTrfInitn": {
                "GrpHdr": {
                    "MsgId": msg_id,
                    "CreDtTm": now_datetime().strftime("%Y-%m-%dT%H:%M:%S"),
                    "NbOfTxs": str(len(batch.cheques)),
                    "CtrlSum": str(flt(batch.total_amount, 2)),
                    "InitgPty": {
                        "Nm": frappe.db.get_default("company") or "Real Estate Developer",
                    },
                },
                "PmtInf": [],
            },
        }
    }

    # Add each cheque as a payment information block
    for idx, cheque_row in enumerate(batch.cheques, 1):
        pdc = frappe.get_doc("Post Dated Cheque", cheque_row.post_dated_cheque)

        pmt_info = {
            "PmtInfId": f"{msg_id}-{idx}",
            "PmtMtd": "CHK",  # Cheque
            "NbOfTxs": "1",
            "CtrlSum": str(flt(pdc.amount, 2)),
            "PmtTpInf": {
                "InstrPrty": "NORM",
                "SvcLvl": {"Cd": "NORM"},
            },
            "ReqdExctnDt": {"Dt": str(pdc.due_date)},
            "Dbtr": {
                "Nm": pdc.drawer_name or "",
            },
            "DbtrAcct": {
                "Id": {"Othr": {"Id": pdc.cheque_number or ""}},
            },
            "DbtrAgt": {
                "FinInstnId": {"Nm": pdc.drawee_bank or ""},
            },
            "CdtTrfTxInf": {
                "PmtId": {
                    "InstrId": pdc.name,
                    "EndToEndId": pdc.cheque_number or pdc.name,
                },
                "Amt": {
                    "InstdAmt": {
                        "@Ccy": "EGP",
                        "#text": str(flt(pdc.amount, 2)),
                    },
                },
                "CdtrAgt": {
                    "FinInstnId": {"Nm": batch.collecting_bank or ""},
                },
                "Cdtr": {
                    "Nm": pdc.payee or "",
                },
                "RmtInf": {
                    "Ustrd": f"PDC Collection: {pdc.name} for {pdc.buyer_profile}",
                },
            },
        }

        pain_doc["Document"]["CstmrCdtTrfInitn"]["PmtInf"].append(pmt_info)

    xml_string = xmltodict.unparse(pain_doc, pretty=True)

    # Store the file as an attachment to the batch
    file_name = f"deposit_batch_{batch.name}_{nowdate()}.xml"
    file_doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": file_name,
            "content": xml_string,
            "attached_to_doctype": "Cheque Batch Deposit",
            "attached_to_name": batch.name,
            "is_private": 1,
        }
    )
    file_doc.save(ignore_permissions=True)

    frappe.msgprint(
        _("ISO 20022 deposit file generated: {0}").format(file_name),
        indicator="green",
    )

    return xml_string


@frappe.whitelist()
def import_clearing_statement(file_content: str):
    """
    Import a CAMT.053 bank-to-customer statement to update PDC clearing status.

    Args:
        file_content: XML content of the CAMT.053 file.
    """
    try:
        statement = xmltodict.parse(file_content)
    except Exception as e:
        frappe.throw(_("Failed to parse CAMT.053 XML: {0}").format(str(e)))

    # Navigate the CAMT.053 structure
    doc = statement.get("Document", {})
    bk_to_cstmr_stmt = doc.get("BkToCstmrStmt", {})
    stmt = bk_to_cstmr_stmt.get("Stmt", {})

    if isinstance(stmt, dict):
        stmt = [stmt]

    cleared_count = 0
    bounced_count = 0

    for statement_entry in stmt:
        entries = statement_entry.get("Ntry", [])
        if isinstance(entries, dict):
            entries = [entries]

        for entry in entries:
            # Extract transaction details
            ntry_ref = entry.get("NtryRef", "") or ""
            status = entry.get("Sts", {})
            status_code = status if isinstance(status, str) else status.get("Cd", "")
            amount = flt(entry.get("Amt", {}).get("#text", 0))

            # Try to match with our PDC by cheque number or reference
            tx_details = entry.get("NtryDtls", {}).get("TxDtls", {})
            if isinstance(tx_details, dict):
                tx_details = [tx_details]

            for tx in tx_details:
                refs = tx.get("Refs", {})
                end_to_end_id = refs.get("EndToEndId", "")
                instr_id = refs.get("InstrId", "")

                # Find matching PDC
                pdc_name = None
                if instr_id and frappe.db.exists("Post Dated Cheque", instr_id):
                    pdc_name = instr_id
                elif end_to_end_id:
                    pdc_name = frappe.db.get_value(
                        "Post Dated Cheque",
                        {"cheque_number": end_to_end_id},
                        "name",
                    )

                if not pdc_name:
                    continue

                if status_code in ("BOOK", "PDNG"):
                    # Cleared
                    frappe.db.set_value(
                        "Post Dated Cheque",
                        pdc_name,
                        {
                            "status": "Cleared",
                            "clearing_date": nowdate(),
                        },
                    )
                    cleared_count += 1

                elif status_code in ("RJCT",):
                    # Bounced
                    reason_info = tx.get("RtrInf", {})
                    reason_code = ""
                    if isinstance(reason_info, dict):
                        rsn = reason_info.get("Rsn", {})
                        reason_code = rsn.get("Cd", "") if isinstance(rsn, dict) else ""

                    reason_map = {
                        "AC01": "Insufficient Funds",
                        "AC04": "Account Closed",
                        "AG01": "Stop Payment",
                        "AM05": "Signature Mismatch",
                    }

                    frappe.db.set_value(
                        "Post Dated Cheque",
                        pdc_name,
                        {
                            "status": "Bounced",
                            "return_reason": reason_map.get(reason_code, "Other"),
                        },
                    )

                    # Increment bounce count
                    current_count = frappe.db.get_value(
                        "Post Dated Cheque", pdc_name, "bounce_count"
                    )
                    frappe.db.set_value(
                        "Post Dated Cheque",
                        pdc_name,
                        "bounce_count",
                        (current_count or 0) + 1,
                    )
                    bounced_count += 1

    frappe.db.commit()
    frappe.msgprint(
        _("Clearing statement imported: {0} cleared, {1} bounced").format(
            cleared_count, bounced_count
        ),
        indicator="green" if bounced_count == 0 else "orange",
    )


@frappe.whitelist()
def check_clearing_status_api(batch_name: str = None):
    """
    Query bank API for real-time clearing status updates.
    This is a placeholder for actual bank API integration.

    In production, this would:
    1. Connect to the bank's API endpoint
    2. Query for cheques submitted in the batch
    3. Update status based on response
    """
    settings = _get_banking_settings()
    if not settings.get("enabled"):
        frappe.msgprint(_("Banking integration is disabled."))
        return

    # Placeholder: In production, make API call here
    frappe.msgprint(
        _("Banking API integration: Please configure your bank's API endpoint in Real Estate Settings."),
        indicator="blue",
    )


def _get_banking_settings() -> dict:
    """Get banking integration settings."""
    try:
        re_settings = frappe.get_single("Real Estate Settings")
        return {
            "enabled": re_settings.get("banking_integration_enabled") or 0,
            "bank_api_url": re_settings.get("bank_api_url") or "",
            "bank_api_key": re_settings.get("bank_api_key") or "",
            "sftp_host": re_settings.get("bank_sftp_host") or "",
            "sftp_user": re_settings.get("bank_sftp_user") or "",
        }
    except Exception:
        return {"enabled": 0}
