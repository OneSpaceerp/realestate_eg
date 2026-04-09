# Copyright (c) 2026, Nest Software Development and contributors
# For license information, please see license.txt

"""Custom Sales Invoice — extends ERPNext Sales Invoice for real estate."""

import frappe
from frappe import _
from frappe.utils import flt
from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice


class CustomSalesInvoice(SalesInvoice):
    """
    Extends standard Sales Invoice with real estate-specific functionality:
    - Links to Property Contract, Property Unit, Buyer Profile
    - Auto-generates ETA e-invoice on submission
    - Adds real estate classification on the invoice
    """

    def validate(self):
        super().validate()
        self._validate_real_estate_fields()

    def on_submit(self):
        super().on_submit()
        self._create_eta_invoice()

    def _validate_real_estate_fields(self):
        """Validate custom real estate fields if they exist."""
        if self.get("property_unit"):
            # Verify unit exists and is under contract or sold
            unit_status = frappe.db.get_value(
                "Property Unit", self.property_unit, "status"
            )
            if unit_status and unit_status not in (
                "Under Contract",
                "Sold",
                "Delivered",
                "Reserved",
            ):
                frappe.msgprint(
                    _(
                        "Warning: Property Unit {0} has status '{1}'. "
                        "Invoice may not be appropriate."
                    ).format(self.property_unit, unit_status),
                    indicator="orange",
                )

    def _create_eta_invoice(self):
        """Auto-generate ETA e-invoice on Sales Invoice submission."""
        try:
            from realestate_eg.api.eta_integration import create_eta_invoice_from_transaction

            # Only create ETA invoice if this is a real estate transaction
            if self.get("property_contract") or self.get("property_unit"):
                items = []
                for item in self.items:
                    items.append(
                        {
                            "description": item.description or item.item_name,
                            "quantity": flt(item.qty),
                            "unit_price": flt(item.rate),
                            "vat_rate": 0,  # Real estate is generally VAT-exempt in Egypt
                            "unit": "EA",
                            "item_code": item.item_code or "",
                        }
                    )

                create_eta_invoice_from_transaction(
                    source_doctype="Sales Invoice",
                    source_name=self.name,
                    items=items,
                )
        except Exception as e:
            frappe.logger("realestate_eg").warning(
                f"Failed to auto-create ETA invoice for {self.name}: {e}"
            )
