# Copyright (c) 2026, Nest Software Development and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate
from frappe.model.document import Document

from realestate_eg.utils.tax_utils import calculate_transfer_tax


class LandParcel(Document):
    """Controller for Land Parcel DocType."""

    def validate(self):
        self._calculate_transfer_tax()
        self._validate_area()

    def before_save(self):
        self._calculate_transfer_tax()

    def on_update(self):
        if self.has_value_changed("status") and self.status == "Acquired":
            self._create_land_asset_gl_entry()

    def _calculate_transfer_tax(self):
        """Auto-calculate transfer tax as 2.5% of total acquisition cost."""
        self.transfer_tax_amount = calculate_transfer_tax(flt(self.total_cost))

    def _validate_area(self):
        """Validate that area is positive."""
        if flt(self.total_area_sqm) <= 0:
            frappe.throw(_("Total Area must be greater than zero."))

    def _create_land_asset_gl_entry(self):
        """
        On status change to 'Acquired', create GL entries to capitalize
        the land as a fixed asset in the Chart of Accounts.
        """
        if frappe.flags.in_import or frappe.flags.in_patch:
            return

        company = frappe.db.get_default("company")
        if not company:
            frappe.msgprint(
                _("Please set a default company to auto-create land asset GL entries."),
                indicator="orange",
            )
            return

        # Get accounts
        fixed_asset_account = frappe.db.get_value(
            "Account",
            {"account_type": "Fixed Asset", "is_group": 0, "company": company},
            "name",
        )

        payable_account = frappe.db.get_value(
            "Company", company, "default_payable_account"
        )

        if not fixed_asset_account or not payable_account:
            frappe.msgprint(
                _("Fixed Asset or Payable account not found. GL entry not created."),
                indicator="orange",
            )
            return

        total_capitalized = (
            flt(self.total_cost)
            + flt(self.transfer_tax_amount)
            + flt(self.legal_fees)
            + flt(self.agency_commission)
        )

        try:
            je = frappe.new_doc("Journal Entry")
            je.company = company
            je.posting_date = self.acquisition_date or nowdate()
            je.voucher_type = "Journal Entry"
            je.user_remark = _("Land acquisition: {0} — {1}").format(
                self.parcel_name, self.name
            )

            # Debit Fixed Asset
            je.append(
                "accounts",
                {
                    "account": fixed_asset_account,
                    "debit_in_account_currency": flt(total_capitalized, 2),
                    "credit_in_account_currency": 0,
                },
            )

            # Credit Payable
            je.append(
                "accounts",
                {
                    "account": payable_account,
                    "debit_in_account_currency": 0,
                    "credit_in_account_currency": flt(total_capitalized, 2),
                },
            )

            je.insert(ignore_permissions=True)
            je.submit()

            frappe.msgprint(
                _("Land asset GL entry created: {0} EGP capitalized as fixed asset.").format(
                    frappe.utils.fmt_money(total_capitalized, currency="EGP")
                ),
                indicator="green",
            )

        except Exception as e:
            frappe.log_error(
                title=f"Land GL Entry Failed: {self.name}",
                message=str(e),
            )
            frappe.msgprint(
                _("Failed to create land asset GL entry: {0}").format(str(e)),
                indicator="red",
            )
