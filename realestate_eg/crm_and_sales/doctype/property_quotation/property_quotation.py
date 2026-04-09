import frappe
from frappe.model.document import Document
from frappe.utils import flt

class PropertyQuotation(Document):
    def validate(self):
        self._calculate()

    def on_submit(self):
        self.status = "Submitted"

    def _calculate(self):
        price = flt(self.property_price)
        dis_amt = price * flt(self.discount_pct) / 100
        self.discount_amount = flt(dis_amt, 2)
        
        net = price - dis_amt
        self.net_price = flt(net, 2)
        
        dp = net * flt(self.down_payment_pct) / 100
        self.down_payment_amount = flt(dp, 2)
        
        if self.payment_plan_months > 0:
            self.installment_amount = flt((net - dp) / self.payment_plan_months, 2)
