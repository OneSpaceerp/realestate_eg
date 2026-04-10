# Copyright (c) 2026, Nest Software Development and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate, cint
from frappe.model.document import Document

from realestate_eg.utils.installment_calculator import generate_installment_schedule


class InstallmentPlan(Document):
    """
    Controller for Installment Plan — the core financial document.

    Lifecycle:
    1. Created from Property Contract on_submit
    2. Schedule auto-generated from calculator engine
    3. Penalties calculated daily by scheduler
    4. Payments tracked via Installment Payment submissions
    5. Plan completes when all schedule rows are Paid
    """

    def validate(self):
        self._calculate_financials()
        self._validate_duration()
        if not self.schedule or len(self.schedule) == 0:
            self._generate_schedule()
        self._update_totals()

    def on_submit(self):
        self._update_unit_status()

    def on_cancel(self):
        self._revert_unit_status()

    def _calculate_financials(self):
        """Calculate down payment and financed amount."""
        self.down_payment_amount = flt(
            flt(self.total_unit_price) * flt(self.down_payment_pct) / 100, 2
        )
        self.financed_amount = flt(
            flt(self.total_unit_price)
            - flt(self.reservation_fee)
            - flt(self.down_payment_amount),
            2,
        )
        if flt(self.financed_amount) < 0:
            frappe.throw(
                _(
                    "Financed amount cannot be negative. "
                    "Check reservation fee and down payment."
                )
            )

    def _validate_duration(self):
        """Validate plan duration is within allowed range."""
        if cint(self.plan_duration_months) < 1:
            frappe.throw(_("Plan duration must be at least 1 month."))
        if cint(self.plan_duration_months) > 180:
            frappe.throw(_("Plan duration cannot exceed 180 months (15 years)."))

    def _generate_schedule(self):
        """Auto-generate installment schedule rows from the calculator engine."""
        schedule_data = generate_installment_schedule(
            financed_amount=flt(self.financed_amount),
            start_date=self.plan_start_date,
            duration_months=cint(self.plan_duration_months),
            frequency=self.frequency,
            admin_fee_pct=flt(self.admin_fee_pct),
            balloon_amount=flt(self.balloon_payment),
            late_penalty_rate=flt(self.late_penalty_rate),
        )

        self.schedule = []
        for row_data in schedule_data:
            self.append(
                "schedule",
                {
                    "due_date": row_data["due_date"],
                    "amount": row_data["amount"],
                    "penalty_amount": 0,
                    "total_due": row_data["amount"],
                    "paid_amount": 0,
                    "balance": row_data["amount"],
                    "status": "Upcoming",
                    "days_overdue": 0,
                },
            )

    def _update_totals(self):
        """Recalculate running totals from schedule rows."""
        total_paid = 0.0
        total_penalties = 0.0
        overdue_amount = 0.0
        last_payment = None

        for row in self.schedule:
            total_paid += flt(row.paid_amount)
            total_penalties += flt(row.penalty_amount)
            if row.status == "Overdue":
                overdue_amount += flt(row.balance)
            if row.payment_date:
                if not last_payment or getdate(row.payment_date) > getdate(last_payment):
                    last_payment = row.payment_date

        self.total_paid = flt(total_paid, 2)
        self.total_outstanding = flt(flt(self.financed_amount) - total_paid, 2)
        self.total_penalties_accrued = flt(total_penalties, 2)
        self.overdue_amount = flt(overdue_amount, 2)
        self.last_payment_date = last_payment

        if flt(self.financed_amount) > 0:
            self.completion_pct = flt(total_paid / flt(self.financed_amount) * 100, 2)
        else:
            self.completion_pct = 0

    def _update_unit_status(self):
        """Update Property Unit status to 'Under Contract'."""
        if self.property_unit:
            frappe.db.set_value(
                "Property Unit",
                self.property_unit,
                {
                    "status": "Under Contract",
                    "current_buyer": self.buyer_profile,
                    "installment_plan": self.name,
                },
            )

    def _revert_unit_status(self):
        """Revert Property Unit status on cancellation."""
        if self.property_unit:
            frappe.db.set_value(
                "Property Unit",
                self.property_unit,
                {
                    "status": "Available",
                    "current_buyer": None,
                    "installment_plan": None,
                },
            )

    @frappe.whitelist()
    def regenerate_schedule(self):
        """Regenerate the installment schedule (admin action)."""
        self._calculate_financials()
        self._generate_schedule()
        self._update_totals()
        self.save()
        frappe.msgprint(
            _("Schedule regenerated with {0} installments.").format(len(self.schedule)),
            indicator="green",
        )

    @frappe.whitelist()
    def get_preview_schedule(self):
        """Generate and return schedule for preview without saving."""
        self._calculate_financials()
        self._generate_schedule()
        return [row.as_dict() for row in self.schedule]
