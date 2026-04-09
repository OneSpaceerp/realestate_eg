# Copyright (c) 2026, Nest Software Development and contributors
import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate, cint, add_months
from frappe.model.document import Document


class PropertyContract(Document):
    """Controller for Property Contract — auto-generates installment plan on submit."""

    def validate(self):
        self._calculate_financials()
        if not self.contract_number:
            self.contract_number = self.name

    def on_submit(self):
        self._create_installment_plan()
        self._update_unit_status()
        self._trigger_eta_invoice()
        self.status = "Active"
        self.db_set("status", "Active", update_modified=False)

    def on_cancel(self):
        self._cancel_installment_plan()
        self._revert_unit_status()
        self.status = "Cancelled"
        self.db_set("status", "Cancelled", update_modified=False)

    def _calculate_financials(self):
        """Calculate down payment and financed amount."""
        self.down_payment_amount = flt(
            flt(self.total_unit_price) * flt(self.down_payment_pct) / 100, 2
        )
        self.financed_amount = flt(
            flt(self.total_unit_price) - flt(self.reservation_fee) - flt(self.down_payment_amount), 2
        )

    def _create_installment_plan(self):
        """Auto-generate Installment Plan on contract submission."""
        if self.contract_type != "Sale":
            return

        if flt(self.financed_amount) <= 0:
            frappe.msgprint(_("No financed amount. Installment plan not created."), indicator="orange")
            return

        plan = frappe.new_doc("Installment Plan")
        plan.property_contract = self.name
        plan.property_unit = self.property_unit
        plan.buyer_profile = self.buyer_profile
        plan.company = self.company
        plan.status = "Active"
        plan.plan_start_date = add_months(getdate(self.contract_date), 1)
        plan.plan_duration_months = cint(self.payment_plan_months)
        plan.frequency = self.installment_frequency
        plan.total_unit_price = flt(self.total_unit_price)
        plan.reservation_fee = flt(self.reservation_fee)
        plan.down_payment_pct = flt(self.down_payment_pct)
        plan.admin_fee_pct = flt(self.admin_fee_pct)
        plan.late_penalty_rate = 2.5  # Default 2.5%/month

        plan.insert(ignore_permissions=True)
        plan.submit()

        self.db_set("installment_plan", plan.name, update_modified=False)

        frappe.msgprint(
            _("Installment Plan {0} created with {1} installments.").format(
                plan.name, len(plan.schedule)
            ),
            indicator="green",
        )

    def _update_unit_status(self):
        """Update Property Unit status to 'Under Contract'."""
        if self.property_unit:
            frappe.db.set_value("Property Unit", self.property_unit, {
                "status": "Under Contract",
                "current_buyer": self.buyer_profile,
            })

    def _revert_unit_status(self):
        """Revert Property Unit status on cancellation."""
        if self.property_unit:
            frappe.db.set_value("Property Unit", self.property_unit, {
                "status": "Available",
                "current_buyer": None,
                "installment_plan": None,
            })

    def _cancel_installment_plan(self):
        """Cancel linked installment plan."""
        if self.installment_plan:
            plan = frappe.get_doc("Installment Plan", self.installment_plan)
            if plan.docstatus == 1:
                plan.cancel()

    def _trigger_eta_invoice(self):
        """Create ETA e-invoice for the contract."""
        try:
            from realestate_eg.api.eta_integration import create_eta_invoice_from_transaction
            create_eta_invoice_from_transaction(
                source_doctype="Property Contract",
                source_name=self.name,
            )
        except Exception as e:
            frappe.logger("realestate_eg").warning(f"ETA invoice creation failed: {e}")


def on_contract_submit(doc, method):
    """Hook called from doc_events."""
    pass

def on_contract_cancel(doc, method):
    """Hook called from doc_events."""
    pass
