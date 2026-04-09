# Copyright (c) 2026, Nest Software Development and contributors
"""Create default PDC-related accounts in Chart of Accounts."""

import frappe
from frappe import _


def execute():
    """Create Notes Receivable, Under Collection, and Wadeea accounts."""
    company = frappe.db.get_default("company")
    if not company:
        return

    receivable_group = frappe.db.get_value(
        "Account",
        {"account_type": "Receivable", "is_group": 1, "company": company},
        "name",
    )

    if not receivable_group:
        receivable_group = frappe.db.get_value(
            "Account",
            {"root_type": "Asset", "is_group": 1, "company": company},
            "name",
        )

    if not receivable_group:
        return

    accounts_to_create = [
        {
            "account_name": "Notes Receivable",
            "parent_account": receivable_group,
            "account_type": "Receivable",
            "company": company,
        },
        {
            "account_name": "Cheques Under Collection",
            "parent_account": receivable_group,
            "account_type": "Receivable",
            "company": company,
        },
        {
            "account_name": "Wadeea Maintenance Deposits",
            "parent_account": receivable_group,
            "account_type": "Receivable",
            "company": company,
        },
    ]

    for acc_data in accounts_to_create:
        if not frappe.db.exists(
            "Account",
            {"account_name": acc_data["account_name"], "company": company},
        ):
            acc = frappe.new_doc("Account")
            acc.update(acc_data)
            acc.insert(ignore_permissions=True)

    frappe.db.commit()
