import frappe
from frappe.model.document import Document
from frappe.utils import add_months

class RefundSchedule(Document):
    def validate(self):
        if not self.refund_payments and self.number_of_payments > 0:
            self._generate()

    def on_submit(self):
        self.status = "Active"

    def _generate(self):
        amount = self.total_refund_amount / self.number_of_payments
        for i in range(self.number_of_payments):
            self.append("refund_payments", {
                "due_date": add_months(self.start_date, i),
                "amount": amount,
                "total_due": amount,
                "balance": amount,
                "status": "Upcoming"
            })
