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
