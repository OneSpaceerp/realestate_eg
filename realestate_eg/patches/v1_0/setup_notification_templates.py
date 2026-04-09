# Copyright (c) 2026, Nest Software Development and contributors
"""Setup notification templates for automated emails."""

import frappe


def execute():
    """Create notification documents for automated email triggers."""
    notifications = [
        {
            "name": "Installment Due Reminder",
            "doctype": "Notification",
            "subject": "Installment Payment Due — {{ doc.name }}",
            "document_type": "Installment Plan",
            "event": "Days Before",
            "days_in_advance": 7,
            "channel": "Email",
            "message": "Your installment payment is due in 7 days.",
            "module": "Real Estate Egypt",
        },
    ]

    for notif_data in notifications:
        if not frappe.db.exists("Notification", notif_data["name"]):
            try:
                notif = frappe.new_doc("Notification")
                notif.update(notif_data)
                notif.insert(ignore_permissions=True)
            except Exception:
                pass

    frappe.db.commit()
