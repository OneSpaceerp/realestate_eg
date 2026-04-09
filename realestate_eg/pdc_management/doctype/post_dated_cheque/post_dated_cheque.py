# Copyright (c) 2026, Nest Software Development and contributors
import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate
from frappe.model.document import Document

from realestate_eg.utils.pdc_lifecycle import (
    validate_status_transition,
    create_pdc_gl_entries,
)


class PostDatedCheque(Document):
    """Controller for Post Dated Cheque with full lifecycle management."""

    def validate(self):
        self._validate_cheque_number()
        self._validate_due_date()

    def before_save(self):
        if self.has_value_changed("status"):
            old_status = self.get_doc_before_save()
            if old_status:
                validate_status_transition(old_status.status, self.status)

    def on_update(self):
        if self.has_value_changed("status"):
            old_doc = self.get_doc_before_save()
            old_status = old_doc.status if old_doc else None
            self._handle_status_change(old_status, self.status)

    def _validate_cheque_number(self):
        if not self.cheque_number or not self.cheque_number.strip():
            frappe.throw(_("Cheque number is required."))

    def _validate_due_date(self):
        if self.due_date and getdate(self.due_date) < getdate("2020-01-01"):
            frappe.throw(_("Due date appears invalid."))

    def _handle_status_change(self, old_status, new_status):
        """Handle GL entries and side effects on status transitions."""
        if frappe.flags.in_import or frappe.flags.in_patch:
            return

        transition_map = {
            ("Received", "In Vault"): "received",
            ("In Vault", "Submitted to Bank"): None,
            ("Submitted to Bank", "Under Collection"): "under_collection",
            ("Under Collection", "Cleared"): "cleared",
            ("Under Collection", "Bounced"): "bounced",
        }

        if old_status:
            transition_key = (old_status, new_status)
            gl_transition = transition_map.get(transition_key)

            if gl_transition:
                create_pdc_gl_entries(
                    pdc_name=self.name,
                    transition=gl_transition,
                    company=self.company,
                )

        # Handle bounced cheque
        if new_status == "Bounced":
            self._handle_bounce()

        # Handle cleared cheque — update installment schedule
        if new_status == "Cleared":
            self._handle_clearing()

    def _handle_bounce(self):
        """Process bounced cheque: create penalty, notify buyer."""
        self.bounce_count = (self.bounce_count or 0) + 1

        # Create a Bounced Cheque Action record
        try:
            frappe.get_doc({
                "doctype": "Bounced Cheque Action",
                "post_dated_cheque": self.name,
                "buyer_profile": self.buyer_profile,
                "bounce_date": nowdate(),
                "bounce_reason": self.return_reason,
                "bounce_count": self.bounce_count,
                "cheque_amount": self.amount,
                "status": "Pending",
                "recommended_action": "Redeposit" if self.bounce_count < 3 else "Legal Action",
            }).insert(ignore_permissions=True)
        except Exception as e:
            frappe.logger("realestate_eg").warning(f"Failed to create bounce action: {e}")

    def _handle_clearing(self):
        """Process cleared cheque: update installment schedule row."""
        self.clearing_date = nowdate()

        if self.installment_plan and self.installment_schedule_row:
            try:
                plan = frappe.get_doc("Installment Plan", self.installment_plan)
                for row in plan.schedule:
                    if row.idx == self.installment_schedule_row:
                        row.paid_amount = flt(row.paid_amount) + flt(self.amount)
                        row.payment_date = nowdate()
                        row.balance = max(0, flt(row.total_due) - flt(row.paid_amount))
                        if flt(row.balance) <= 0:
                            row.status = "Paid"
                        else:
                            row.status = "Partially Paid"
                        break

                total_paid = sum(flt(r.paid_amount) for r in plan.schedule)
                plan.total_paid = flt(total_paid, 2)
                plan.total_outstanding = flt(plan.financed_amount - total_paid, 2)
                if flt(plan.total_outstanding) <= 0:
                    plan.status = "Fully Paid"

                plan.flags.ignore_validate = True
                plan.save(ignore_permissions=True)
            except Exception as e:
                frappe.logger("realestate_eg").warning(f"Failed to update schedule on clear: {e}")

    @frappe.whitelist()
    def scan_with_ocr(self):
        """Trigger OCR scan of the cheque image."""
        if not self.cheque_image:
            frappe.throw(_("Please attach a cheque image first."))

        from realestate_eg.api.ocr_service import scan_cheque
        result = scan_cheque(image_url=self.cheque_image, pdc_name=self.name)
        
        if result.get("status") == "success":
            frappe.msgprint(
                _("OCR scan complete. Verified: {0}").format(
                    result.get("verification", {}).get("is_verified", "N/A")
                ),
                indicator="green" if result.get("verification", {}).get("is_verified") else "orange",
            )
        return result


def on_pdc_update(doc, method):
    """Hook called from doc_events on PDC update."""
    pass  # Logic is in on_update of the controller
