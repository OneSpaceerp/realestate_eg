import frappe
from frappe.model.document import Document
from frappe.utils import date_diff, add_months
from math import ceil

class LeaseContract(Document):
    def validate(self):
        if not self.rent_schedule:
            self._generate_schedule()

    def on_submit(self):
        self.status = "Active"
        frappe.db.set_value("Property Unit", self.property_unit, "status", "Rented")
        
    def on_cancel(self):
        self.status = "Terminated"
        frappe.db.set_value("Property Unit", self.property_unit, "status", "Available")

    def _generate_schedule(self):
        months = ceil(date_diff(self.lease_end_date, self.lease_start_date) / 30.0)
        current_rent = self.monthly_rent
        
        for i in range(months):
            if i > 0 and i % 12 == 0 and self.annual_increase_pct:
                current_rent *= (1 + self.annual_increase_pct / 100)
            
            self.append("rent_schedule", {
                "due_date": add_months(self.lease_start_date, i),
                "amount": current_rent,
                "total_due": current_rent,
                "balance": current_rent,
                "status": "Upcoming"
            })
