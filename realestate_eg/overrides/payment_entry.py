# Copyright (c) 2026, Nest Software Development and contributors
# For license information, please see license.txt

"""Custom Payment Entry — extends ERPNext Payment Entry for installment tracking."""

import frappe
from frappe import _
from frappe.utils import flt, getdate
from erpnext.accounts.doctype.payment_entry.payment_entry import PaymentEntry


class CustomPaymentEntry(PaymentEntry):
    """
    Extends standard Payment Entry:
    - Auto-updates installment schedule row when payment is reconciled
    - Links payment to PDC if applicable
    - Triggers ETA e-receipt generation
    """

    def validate(self):
        super().validate()

    def on_submit(self):
        super().on_submit()
        self._update_installment_schedule()
        self._create_eta_receipt()

    def on_cancel(self):
        super().on_cancel()
        self._reverse_installment_schedule()

    def _update_installment_schedule(self):
        """
        If this payment is linked to an installment schedule row,
        update the row's paid_amount and status.
        """
        if frappe.flags.in_import or frappe.flags.in_patch:
            return

        installment_plan = self.get("custom_installment_plan")
        schedule_idx = self.get("custom_installment_schedule_idx")

        if not installment_plan or not schedule_idx:
            return

        try:
            plan = frappe.get_doc("Installment Plan", installment_plan)
            for row in plan.schedule:
                if row.idx == int(schedule_idx):
                    row.paid_amount = flt(row.paid_amount) + flt(self.paid_amount)
                    row.payment_date = self.posting_date
                    row.payment_entry = self.name
                    row.balance = flt(row.total_due) - flt(row.paid_amount)

                    if flt(row.balance) <= 0:
                        row.status = "Paid"
                        row.balance = 0
                    else:
                        row.status = "Partially Paid"

                    break

            # Recalculate plan totals
            total_paid = sum(flt(r.paid_amount) for r in plan.schedule)
            plan.total_paid = flt(total_paid, 2)
            plan.total_outstanding = flt(plan.financed_amount - total_paid, 2)

            # Check if fully paid
            if flt(plan.total_outstanding) <= 0:
                plan.status = "Fully Paid"

            plan.flags.ignore_validate = True
            plan.save(ignore_permissions=True)

        except Exception as e:
            frappe.logger("realestate_eg").warning(
                f"Failed to update installment schedule from payment {self.name}: {e}"
            )

    def _reverse_installment_schedule(self):
        """Reverse installment schedule updates on payment cancellation."""
        installment_plan = self.get("custom_installment_plan")
        schedule_idx = self.get("custom_installment_schedule_idx")

        if not installment_plan or not schedule_idx:
            return

        try:
            plan = frappe.get_doc("Installment Plan", installment_plan)
            for row in plan.schedule:
                if row.idx == int(schedule_idx):
                    row.paid_amount = max(0, flt(row.paid_amount) - flt(self.paid_amount))
                    row.balance = flt(row.total_due) - flt(row.paid_amount)
                    row.payment_entry = None
                    row.payment_date = None

                    if flt(row.paid_amount) <= 0:
                        today = getdate()
                        if getdate(row.due_date) < today:
                            row.status = "Overdue"
                        elif getdate(row.due_date) == today:
                            row.status = "Due"
                        else:
                            row.status = "Upcoming"
                    else:
                        row.status = "Partially Paid"

                    break

            # Recalculate plan totals
            total_paid = sum(flt(r.paid_amount) for r in plan.schedule)
            plan.total_paid = flt(total_paid, 2)
            plan.total_outstanding = flt(plan.financed_amount - total_paid, 2)

            if plan.status == "Fully Paid":
                plan.status = "Active"

            plan.flags.ignore_validate = True
            plan.save(ignore_permissions=True)

        except Exception as e:
            frappe.logger("realestate_eg").warning(
                f"Failed to reverse installment schedule from payment {self.name}: {e}"
            )

    def _create_eta_receipt(self):
        """Auto-generate ETA e-receipt for the payment."""
        if not self.get("custom_installment_plan"):
            return

        try:
            from realestate_eg.api.eta_integration import create_eta_invoice_from_transaction

            create_eta_invoice_from_transaction(
                source_doctype="Payment Entry",
                source_name=self.name,
            )
        except Exception as e:
            frappe.logger("realestate_eg").warning(
                f"Failed to create ETA receipt for payment {self.name}: {e}"
            )
