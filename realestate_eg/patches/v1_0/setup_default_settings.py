# Copyright (c) 2026, Nest Software Development and contributors
"""Setup default Real Estate Settings singleton."""

import frappe


def execute():
    """Ensure Real Estate Settings document exists."""
    if not frappe.db.exists("Real Estate Settings", "Real Estate Settings"):
        if frappe.db.exists("DocType", "Real Estate Settings"):
            doc = frappe.new_doc("Real Estate Settings")
            doc.insert(ignore_permissions=True)
            frappe.db.commit()
