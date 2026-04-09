import frappe
from frappe.model.document import Document
from frappe.utils import flt

class UtilityBilling(Document):
    def validate(self):
        self._calculate()

    def on_submit(self):
        self.status = "Unpaid"

    def _calculate(self):
        if self.meter_reading_current >= self.meter_reading_previous:
            self.consumption = self.meter_reading_current - self.meter_reading_previous
            self.total_amount = self.consumption * flt(self.rate_per_unit)
