import frappe
from frappe.model.document import Document
from frappe.utils import flt

class LeaseRenewal(Document):
    def validate(self):
        self._calculate()

    def on_submit(self):
        self.status = "Approved"
        self._create_new_lease()

    def _calculate(self):
        if self.old_rent:
            self.new_rent = flt(self.old_rent) * (1 + flt(self.increase_pct)/100)

    def _create_new_lease(self):
        orig = frappe.get_doc("Lease Contract", self.original_lease)
        orig.status = "Renewed"
        orig.save()
        
        new_lease = frappe.copy_doc(orig)
        new_lease.lease_start_date = self.new_lease_start
        new_lease.lease_end_date = self.new_lease_end
        new_lease.monthly_rent = self.new_rent
        new_lease.security_deposit = self.new_security_deposit
        new_lease.rent_schedule = []
        new_lease.status = "Active"
        new_lease.insert(ignore_permissions=True)
        new_lease.submit()
        
        self.db_set("new_lease_contract", new_lease.name)
