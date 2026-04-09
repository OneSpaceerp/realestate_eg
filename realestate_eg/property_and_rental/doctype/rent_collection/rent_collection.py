import frappe
from frappe.model.document import Document
from frappe.utils import flt

class RentCollection(Document):
    def on_submit(self):
        self._update_schedule()

    def on_cancel(self):
        self._reverse_schedule()

    def _update_schedule(self):
        if not self.schedule_row_idx: return
        lease = frappe.get_doc("Lease Contract", self.lease_contract)
        for row in lease.rent_schedule:
            if row.idx == self.schedule_row_idx:
                row.paid_amount = flt(row.paid_amount) + flt(self.amount)
                row.balance = flt(row.total_due) - flt(row.paid_amount)
                if row.balance <= 0:
                    row.status = "Paid"
                else:
                    row.status = "Partially Paid"
                break
        lease.flags.ignore_validate = True
        lease.save(ignore_permissions=True)

    def _reverse_schedule(self):
        if not self.schedule_row_idx: return
        lease = frappe.get_doc("Lease Contract", self.lease_contract)
        for row in lease.rent_schedule:
            if row.idx == self.schedule_row_idx:
                row.paid_amount = max(0, flt(row.paid_amount) - flt(self.amount))
                row.balance = flt(row.total_due) - flt(row.paid_amount)
                if row.balance > 0:
                    row.status = "Upcoming"
                break
        lease.flags.ignore_validate = True
        lease.save(ignore_permissions=True)
