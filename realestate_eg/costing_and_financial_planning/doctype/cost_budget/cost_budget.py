import frappe
from frappe.model.document import Document
from frappe.utils import flt

class CostBudget(Document):
    def validate(self):
        self._calculate()

    def _calculate(self):
        tot_est = 0.0
        tot_act = 0.0
        for row in self.cost_lines:
            row.variance = flt(row.estimated_cost) - flt(row.actual_cost)
            tot_est += flt(row.estimated_cost)
            tot_act += flt(row.actual_cost)
        self.total_estimated_cost = tot_est
        self.total_actual_cost = tot_act
