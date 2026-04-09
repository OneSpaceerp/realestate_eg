# Copyright (c) 2026, Nest Software Development and contributors
import frappe
from frappe import _
from frappe.utils import flt
from frappe.model.document import Document
from realestate_eg.utils.cancellation_engine import calculate_deduction, process_cancellation


class UnitCancellation(Document):
    def validate(self):
        self._calculate_deductions()

    def on_submit(self):
        pass  # Workflow manages status transitions

    def on_update_after_submit(self):
        if self.status == "Approved":
            process_cancellation(self.name)

    def _calculate_deductions(self):
        result = calculate_deduction(
            total_amount_paid=flt(self.total_amount_paid),
            project_completion_pct=flt(self.project_completion_pct),
            is_developer_delay=self.is_developer_delay,
        )
        self.deduction_pct = result["deduction_pct"]
        self.deduction_amount = result["deduction_amount"]
        self.net_refund_amount = result["net_refund_amount"]


def on_cancellation_submit(doc, method):
    pass
