# Copyright (c) 2026, Nest Software Development and contributors
import frappe
from frappe import _
from frappe.utils import flt, cint
from frappe.model.document import Document

class RealEstateProject(Document):
    def validate(self):
        self._update_unit_count()
        self._update_completion_pct()

    def _update_unit_count(self):
        self.total_units = frappe.db.count("Property Unit", {"project": self.name}) or 0

    def _update_completion_pct(self):
        milestones = frappe.get_all(
            "Construction Milestone",
            filters={"project": self.name, "status": "Completed"},
            fields=["completion_contribution"],
        )
        total_contribution = sum(flt(m.completion_contribution) for m in milestones)
        self.completion_pct = min(flt(total_contribution, 2), 100)
