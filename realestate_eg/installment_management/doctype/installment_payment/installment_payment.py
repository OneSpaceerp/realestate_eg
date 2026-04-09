# Copyright (c) 2026, Nest Software Development and contributors
import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate
from frappe.model.document import Document


class InstallmentPayment(Document):
    """Controller for Installment Payment — creates Payment Entry and updates schedule."""

    def validate(self):
        self._validate_amount()

    def on_submit(self):
        self._create_payment_entry()
        self._update_installment_schedule()
        self._trigger_eta_receipt()

    def on_cancel(self):
        self._reverse_installment_schedule()

    def _validate_amount(self):
        if flt(self.amount) <= 0:
            frappe.throw(_("Payment amount must be greater than zero."))

    def _create_payment_entry(self):
        """Create a standard ERPNext Payment Entry for GL integration."""
        plan = frappe.get_doc("Installment Plan", self.installment_plan)
        buyer = frappe.get_doc("Buyer Profile", self.buyer_profile)

        try:
            pe = frappe.new_doc("Payment Entry")
            pe.payment_type = "Receive"
            pe.company = self.company
            pe.posting_date = self.payment_date
            pe.mode_of_payment = self.payment_method
            pe.party_type = "Customer"
            pe.party = buyer.customer
            pe.paid_amount = flt(self.amount)
            pe.received_amount = flt(self.amount)
            pe.source_exchange_rate = 1
            pe.target_exchange_rate = 1

            # Set accounts
            pe.paid_to = frappe.db.get_value(
                "Company", self.company, "default_cash_account"
            ) or frappe.db.get_value(
                "Account", {"account_type": "Cash", "is_group": 0, "company": self.company}
            )
            pe.paid_from = frappe.db.get_value(
                "Company", self.company, "default_receivable_account"
            )

            pe.reference_no = self.name
            pe.reference_date = self.payment_date

            # Custom fields for linking back
            pe.custom_installment_plan = self.installment_plan
            pe.custom_installment_schedule_idx = self.schedule_row_idx

            pe.insert(ignore_permissions=True)
            pe.submit()

            self.db_set("payment_entry", pe.name, update_modified=False)

        except Exception as e:
            frappe.log_error(
                title=f"Payment Entry Creation Failed: {self.name}",
                message=str(e),
            )
            frappe.msgprint(
                _("Warning: Could not create Payment Entry: {0}. Manual creation may be needed.").format(str(e)),
                indicator="orange",
            )

    def _update_installment_schedule(self):
        """Update the corresponding installment schedule row."""
        if not self.schedule_row_idx:
            return

        plan = frappe.get_doc("Installment Plan", self.installment_plan)
        for row in plan.schedule:
            if row.idx == self.schedule_row_idx:
                row.paid_amount = flt(row.paid_amount) + flt(self.amount)
                row.payment_date = self.payment_date
                row.payment_entry = self.payment_entry
                row.balance = max(0, flt(row.total_due) - flt(row.paid_amount))

                if flt(row.balance) <= 0:
                    row.status = "Paid"
                    row.balance = 0
                else:
                    row.status = "Partially Paid"
                break

        # Recalculate totals
        total_paid = sum(flt(r.paid_amount) for r in plan.schedule)
        plan.total_paid = flt(total_paid, 2)
        plan.total_outstanding = flt(plan.financed_amount - total_paid, 2)
        plan.last_payment_date = self.payment_date

        if flt(plan.total_outstanding) <= 0:
            plan.status = "Fully Paid"
            plan.completion_pct = 100
        else:
            plan.completion_pct = flt(total_paid / flt(plan.financed_amount) * 100, 2)

        plan.flags.ignore_validate = True
        plan.save(ignore_permissions=True)

    def _reverse_installment_schedule(self):
        """Reverse schedule updates on payment cancellation."""
        if not self.schedule_row_idx:
            return

        plan = frappe.get_doc("Installment Plan", self.installment_plan)
        for row in plan.schedule:
            if row.idx == self.schedule_row_idx:
                row.paid_amount = max(0, flt(row.paid_amount) - flt(self.amount))
                row.balance = flt(row.total_due) - flt(row.paid_amount)
                if flt(row.paid_amount) <= 0:
                    row.status = "Overdue" if getdate(row.due_date) < getdate(nowdate()) else "Upcoming"
                    row.payment_entry = None
                    row.payment_date = None
                else:
                    row.status = "Partially Paid"
                break

        total_paid = sum(flt(r.paid_amount) for r in plan.schedule)
        plan.total_paid = flt(total_paid, 2)
        plan.total_outstanding = flt(plan.financed_amount - total_paid, 2)
        if plan.status == "Fully Paid":
            plan.status = "Active"

        plan.flags.ignore_validate = True
        plan.save(ignore_permissions=True)

    def _trigger_eta_receipt(self):
        """Create ETA e-receipt for the payment."""
        try:
            from realestate_eg.api.eta_integration import create_eta_invoice_from_transaction
            create_eta_invoice_from_transaction(
                source_doctype="Installment Payment",
                source_name=self.name,
            )
        except Exception as e:
            frappe.logger("realestate_eg").warning(f"ETA receipt creation failed: {e}")


def on_payment_submit(doc, method):
    """Hook called from doc_events on Installment Payment submit."""
    pass  # Logic is in on_submit of the controller


def on_payment_cancel(doc, method):
    """Hook called from doc_events on Installment Payment cancel."""
    pass  # Logic is in on_cancel of the controller
