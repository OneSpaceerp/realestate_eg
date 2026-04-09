import frappe
from frappe.model.document import Document
from frappe.utils import flt

class PlanRestructuring(Document):
    def validate(self):
        self._calculate()

    def on_submit(self):
        self.status = "Approved"
        self.db_set("status", "Approved", update_modified=False)
        self._execute_restructure()

    def _calculate(self):
        base = flt(self.original_outstanding)
        pct_fee = base * flt(self.restructure_fee_pct) / 100
        self.new_financed_amount = base + pct_fee + flt(self.restructure_fee_amount)

        if self.new_duration_months > 0:
            freq_map = {"Monthly": 1, "Quarterly": 3, "Semi-Annual": 6, "Annual": 12}
            divisor = self.new_duration_months / freq_map.get(self.new_frequency, 1)
            if divisor > 0:
                self.new_installment_amount = self.new_financed_amount / divisor

    def _execute_restructure(self):
        plan = frappe.get_doc("Installment Plan", self.installment_plan)
        plan.status = "Restructured"
        plan.flags.ignore_validate = True
        plan.save(ignore_permissions=True)

        new_plan = frappe.copy_doc(plan)
        new_plan.status = "Active"
        new_plan.plan_duration_months = self.new_duration_months
        new_plan.frequency = self.new_frequency
        new_plan.total_unit_price = self.new_financed_amount
        new_plan.down_payment_pct = 0
        new_plan.reservation_fee = 0
        new_plan.financed_amount = self.new_financed_amount
        new_plan.total_paid = 0
        new_plan.total_outstanding = self.new_financed_amount
        new_plan.schedule = []
        new_plan.insert(ignore_permissions=True)
        new_plan.submit()
        
        frappe.msgprint(f"Created new restructuring plan: {new_plan.name}", indicator="green")
