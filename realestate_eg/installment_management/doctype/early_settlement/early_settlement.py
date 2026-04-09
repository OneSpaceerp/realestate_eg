import frappe
from frappe.model.document import Document
from frappe.utils import flt

class EarlySettlement(Document):
    def validate(self):
        self._calculate()

    def on_submit(self):
        self.status = "Approved"
        self.db_set("status", "Approved", update_modified=False)
        self._execute_settlement()

    def _calculate(self):
        base = flt(self.original_outstanding)
        dis = base * flt(self.discount_pct) / 100
        self.discount_amount = flt(dis, 2)
        self.net_settlement_amount = flt(base - dis, 2)

    def _execute_settlement(self):
        plan = frappe.get_doc("Installment Plan", self.installment_plan)
        for row in plan.schedule:
            if row.status not in ("Paid", "Waived"):
                if self.discount_pct > 0 and self.net_settlement_amount == 0:
                     row.status = "Waived"
                     row.balance = 0
        plan.status = "Fully Paid"
        plan.flags.ignore_validate = True
        plan.save(ignore_permissions=True)
