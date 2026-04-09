import frappe
from frappe.model.document import Document
from frappe import _

class PropertyDelivery(Document):
    def validate(self):
        if not self.all_installments_paid and self.status == "Delivered":
            frappe.throw(_("Cannot deliver unit unless all installments are marked as paid."))
        if not self.maintenance_deposit_paid and self.status == "Delivered":
            frappe.throw(_("Cannot deliver unit unless maintenance deposit (Wadeea) is marked as paid."))

    def on_submit(self):
        if self.status == "Delivered":
            frappe.db.set_value("Property Unit", self.property_unit, "status", "Delivered")
            
    def on_cancel(self):
        frappe.db.set_value("Property Unit", self.property_unit, "status", "Sold")
