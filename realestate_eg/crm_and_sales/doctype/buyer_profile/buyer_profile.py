# Copyright (c) 2026, Nest Software Development and contributors
import frappe
from frappe import _
from frappe.utils import flt, cint
from frappe.model.document import Document

class BuyerProfile(Document):
    def validate(self):
        self._validate_national_id()

    def _validate_national_id(self):
        if self.national_id and len(self.national_id) != 14 and self.nationality == "Egyptian":
            frappe.msgprint(
                _("Egyptian National ID must be exactly 14 digits."),
                indicator="orange",
            )

    def update_financials(self):
        """Called automatically whenever the buyer's Installment Plans are saved or paid."""
        # Calculate active outstanding balance
        plans = frappe.get_all(
            "Installment Plan",
            filters={"buyer_profile": self.name, "status": ("in", ["Active", "Defaulted"])},
            fields=["total_outstanding", "property_unit"]
        )
        total_outstanding = sum(flt(p.total_outstanding) for p in plans)

        # Count total distinct units owned (Active, Defaulted, or Fully Paid)
        paid_plans = frappe.get_all(
            "Installment Plan",
            filters={"buyer_profile": self.name, "status": "Fully Paid"},
            fields=["property_unit"]
        )
        
        all_units = set()
        for p in plans + paid_plans:
            if p.property_unit:
                all_units.add(p.property_unit)

        self.db_set("total_outstanding", flt(total_outstanding, 2))
        self.db_set("total_units_owned", len(all_units))
