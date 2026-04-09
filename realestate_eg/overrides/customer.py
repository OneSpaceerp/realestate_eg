# Copyright (c) 2026, Nest Software Development and contributors
# For license information, please see license.txt

"""Custom Customer — extends ERPNext Customer for real estate buyer profiles."""

import frappe
from frappe import _
from frappe.utils import flt, cint
from erpnext.selling.doctype.customer.customer import Customer


class CustomCustomer(Customer):
    """
    Extends standard Customer with real estate-specific functionality:
    - Links to Buyer Profile for extended buyer data
    - Auto-calculates total units owned and outstanding balance
    """

    def validate(self):
        super().validate()

    def on_update(self):
        super().on_update()
        self._update_buyer_profile_stats()

    def _update_buyer_profile_stats(self):
        """Update linked Buyer Profile with aggregate statistics."""
        if frappe.flags.in_import or frappe.flags.in_patch:
            return

        buyer_profile = frappe.db.get_value(
            "Buyer Profile",
            {"customer": self.name},
            "name",
        )

        if not buyer_profile:
            return

        # Count units linked to this buyer
        total_units = frappe.db.count(
            "Property Unit",
            {"current_buyer": buyer_profile},
        )

        # Sum outstanding balance from active installment plans
        outstanding = frappe.db.sql(
            """
            SELECT COALESCE(SUM(total_outstanding), 0) as total
            FROM `tabInstallment Plan`
            WHERE buyer_profile = %s AND status = 'Active'
            """,
            buyer_profile,
        )[0][0]

        frappe.db.set_value(
            "Buyer Profile",
            buyer_profile,
            {
                "total_units_owned": cint(total_units),
                "total_outstanding_balance": flt(outstanding, 2),
            },
            update_modified=False,
        )


def get_dashboard_data(data):
    """Override Customer dashboard to show real estate-related links."""
    data["non_standard_fieldnames"] = data.get("non_standard_fieldnames", {})
    data["non_standard_fieldnames"]["Buyer Profile"] = "customer"

    data["transactions"] = data.get("transactions", [])
    data["transactions"].append(
        {
            "label": _("Real Estate"),
            "items": [
                "Buyer Profile",
                "Property Contract",
                "Installment Plan",
                "Post Dated Cheque",
            ],
        }
    )

    return data
