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

@frappe.whitelist()
def trigger_cost_allocation(project_name, cost_type, total_cost, method="By Market Value"):
    from realestate_eg.utils.cost_allocation import apply_allocation_to_units
    
    frappe.has_permission("Real Estate Project", "write", throw=True)
    
    # Strip commas if passed as formatted string
    if isinstance(total_cost, str):
        total_cost = total_cost.replace(",", "")
        
    total_cost = flt(total_cost)
    
    allocations = apply_allocation_to_units(
        project_name=project_name,
        cost_type=cost_type,
        total_cost=total_cost,
        method=method
    )
    
    return allocations
