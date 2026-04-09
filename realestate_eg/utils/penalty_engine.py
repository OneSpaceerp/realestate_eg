# Copyright (c) 2026, Nest Software Development and contributors
# For license information, please see license.txt

"""
Penalty Engine — Late fee calculation and dunning automation.

Egyptian real estate penalty rules:
- Late fee = outstanding × penalty_rate × (days_overdue / 30)
- Dunning sequence: Day 7 (SMS), Day 14 (Email), Day 30 (Formal), Day 60 (Warning), Day 90 (Legal)
- At 90 days: auto-flag for legal review
"""

import frappe
from frappe import _
from frappe.utils import (
    add_days,
    date_diff,
    flt,
    getdate,
    nowdate,
    cint,
    now_datetime,
)


# Dunning escalation thresholds in days
DUNNING_SEQUENCE = [
    {"days": 7, "level": "Friendly Reminder", "channel": "sms"},
    {"days": 14, "level": "Formal Notice", "channel": "email"},
    {"days": 30, "level": "Warning", "channel": "email"},
    {"days": 60, "level": "Legal Notice", "channel": "email"},
    {"days": 90, "level": "Default Declaration", "channel": "legal"},
]


def calculate_late_fee(
    outstanding_amount: float,
    penalty_rate_pct: float,
    days_overdue: int,
) -> float:
    """
    Calculate late fee per Egyptian market convention.

    Formula: outstanding × (penalty_rate / 100) × (days_overdue / 30)

    Args:
        outstanding_amount: Amount still owed.
        penalty_rate_pct: Monthly penalty rate (e.g., 2.5 = 2.5% per month).
        days_overdue: Number of days past the due date.

    Returns:
        Late fee amount rounded to 2 decimal places.
    """
    if days_overdue <= 0 or flt(outstanding_amount) <= 0:
        return 0.0

    fee = flt(outstanding_amount) * (flt(penalty_rate_pct) / 100) * (cint(days_overdue) / 30)
    return flt(fee, 2)


@frappe.whitelist()
def check_overdue_installments():
    """
    Daily scheduler job: identify overdue installments, calculate penalties,
    and trigger dunning notifications.

    This job is idempotent — safe to run multiple times.
    """
    today = getdate(nowdate())

    # Get all active installment plans
    active_plans = frappe.get_all(
        "Installment Plan",
        filters={"status": "Active"},
        fields=["name", "late_penalty_rate", "buyer_profile", "property_unit"],
    )

    for plan_data in active_plans:
        plan = frappe.get_doc("Installment Plan", plan_data.name)
        plan_modified = False

        for row in plan.schedule:
            if row.status in ("Paid", "Waived"):
                continue

            due_date = getdate(row.due_date)
            if due_date >= today:
                # Not yet due — mark as Due if it's today
                if due_date == today and row.status == "Upcoming":
                    row.status = "Due"
                    plan_modified = True
                continue

            # Mark as overdue
            days_overdue = date_diff(today, due_date)

            if row.status != "Overdue":
                row.status = "Overdue"
                plan_modified = True

            row.days_overdue = days_overdue

            # Calculate penalty
            outstanding = flt(row.amount) - flt(row.paid_amount)
            new_penalty = calculate_late_fee(
                outstanding_amount=outstanding,
                penalty_rate_pct=flt(plan.late_penalty_rate),
                days_overdue=days_overdue,
            )

            if flt(new_penalty, 2) != flt(row.penalty_amount, 2):
                row.penalty_amount = new_penalty
                row.total_due = flt(row.amount) + flt(new_penalty)
                row.balance = flt(row.total_due) - flt(row.paid_amount)
                plan_modified = True

            # Trigger dunning notifications based on escalation thresholds
            _trigger_dunning_if_needed(plan_data, row, days_overdue)

        if plan_modified:
            # Update totals on the plan
            _update_plan_totals(plan)
            plan.flags.ignore_validate = True
            plan.save(ignore_permissions=True)

    frappe.db.commit()
    frappe.logger("realestate_eg").info(
        f"Overdue check complete: processed {len(active_plans)} active plans"
    )


def _trigger_dunning_if_needed(plan_data: dict, schedule_row, days_overdue: int):
    """
    Send dunning notifications based on escalation thresholds.
    Uses frappe.flags to track what has already been sent for this row.
    """
    for threshold in DUNNING_SEQUENCE:
        if days_overdue < threshold["days"]:
            break

        # Check if we've already sent this level for this row
        flag_key = f"dunning_{schedule_row.name}_{threshold['days']}"
        already_sent = frappe.db.get_value(
            "Comment",
            {
                "reference_doctype": "Installment Plan",
                "reference_name": plan_data.name,
                "comment_type": "Info",
                "content": ["like", f"%{flag_key}%"],
            },
        )

        if already_sent:
            continue

        if threshold["channel"] == "sms":
            _send_sms_reminder(plan_data, schedule_row, threshold)
        elif threshold["channel"] == "email":
            _send_email_reminder(plan_data, schedule_row, threshold)
        elif threshold["channel"] == "legal":
            _flag_for_legal_review(plan_data, schedule_row, threshold)

        # Log that we sent this dunning level
        frappe.get_doc(
            {
                "doctype": "Comment",
                "comment_type": "Info",
                "reference_doctype": "Installment Plan",
                "reference_name": plan_data.name,
                "content": _(
                    "Dunning notification sent: {0} ({1} days overdue) — {2}"
                ).format(threshold["level"], days_overdue, flag_key),
            }
        ).insert(ignore_permissions=True)


def _send_sms_reminder(plan_data: dict, schedule_row, threshold: dict):
    """Send SMS reminder for overdue installment."""
    try:
        buyer = frappe.get_doc("Buyer Profile", plan_data.buyer_profile)
        customer = frappe.get_doc("Customer", buyer.customer)

        phone = buyer.phone or customer.mobile_no
        if not phone:
            return

        message = _(
            "Dear {0}, your installment of {1} EGP for unit {2} was due on {3}. "
            "Please arrange payment to avoid penalties. Ref: {4}"
        ).format(
            buyer.buyer_name or customer.customer_name,
            frappe.utils.fmt_money(schedule_row.amount, currency="EGP"),
            plan_data.property_unit,
            frappe.utils.format_date(schedule_row.due_date),
            plan_data.name,
        )

        from realestate_eg.api.sms_gateway import send_sms

        send_sms(phone_number=phone, message=message)

    except Exception as e:
        frappe.logger("realestate_eg").warning(
            f"Failed to send SMS reminder for {plan_data.name}: {e}"
        )


def _send_email_reminder(plan_data: dict, schedule_row, threshold: dict):
    """Send email reminder for overdue installment."""
    try:
        buyer = frappe.get_doc("Buyer Profile", plan_data.buyer_profile)
        customer = frappe.get_doc("Customer", buyer.customer)

        email = buyer.email or customer.email_id
        if not email:
            return

        template_map = {
            14: "installment_reminder",
            30: "installment_reminder",
            60: "installment_reminder",
        }

        template_name = template_map.get(threshold["days"], "installment_reminder")

        frappe.sendmail(
            recipients=[email],
            subject=_("Installment Payment {0} — {1}").format(
                threshold["level"], plan_data.name
            ),
            template=template_name,
            args={
                "buyer_name": buyer.buyer_name or customer.customer_name,
                "amount": frappe.utils.fmt_money(schedule_row.amount, currency="EGP"),
                "due_date": frappe.utils.format_date(schedule_row.due_date),
                "days_overdue": schedule_row.days_overdue,
                "penalty_amount": frappe.utils.fmt_money(
                    schedule_row.penalty_amount, currency="EGP"
                ),
                "total_due": frappe.utils.fmt_money(
                    schedule_row.total_due, currency="EGP"
                ),
                "plan_name": plan_data.name,
                "property_unit": plan_data.property_unit,
                "level": threshold["level"],
            },
            now=True,
        )
    except Exception as e:
        frappe.logger("realestate_eg").warning(
            f"Failed to send email reminder for {plan_data.name}: {e}"
        )


def _flag_for_legal_review(plan_data: dict, schedule_row, threshold: dict):
    """Flag account for legal review at 90+ days overdue."""
    frappe.get_doc(
        {
            "doctype": "ToDo",
            "description": _(
                "LEGAL REVIEW REQUIRED: Installment plan {0} for unit {1} is {2} days overdue. "
                "Outstanding: {3} EGP. Penalty accrued: {4} EGP."
            ).format(
                plan_data.name,
                plan_data.property_unit,
                schedule_row.days_overdue,
                frappe.utils.fmt_money(schedule_row.balance, currency="EGP"),
                frappe.utils.fmt_money(schedule_row.penalty_amount, currency="EGP"),
            ),
            "reference_type": "Installment Plan",
            "reference_name": plan_data.name,
            "assigned_by": "Administrator",
            "priority": "High",
            "status": "Open",
        }
    ).insert(ignore_permissions=True)

    # Send notification to legal role
    legal_users = frappe.get_all(
        "Has Role",
        filters={"role": "Legal Counsel", "parenttype": "User"},
        fields=["parent"],
    )
    for user in legal_users:
        frappe.publish_realtime(
            "eval_js",
            f"frappe.show_alert({{message: '{_('Legal review required for')} {plan_data.name}', indicator: 'red'}})",
            user=user.parent,
        )


def _update_plan_totals(plan):
    """Recalculate plan-level totals from schedule rows."""
    total_paid = 0.0
    total_penalties = 0.0
    overdue_amount = 0.0

    for row in plan.schedule:
        total_paid += flt(row.paid_amount)
        total_penalties += flt(row.penalty_amount)
        if row.status == "Overdue":
            overdue_amount += flt(row.balance)

    plan.total_paid = flt(total_paid, 2)
    plan.total_penalties_accrued = flt(total_penalties, 2)
    plan.overdue_amount = flt(overdue_amount, 2)
    plan.total_outstanding = flt(plan.financed_amount - total_paid, 2)


@frappe.whitelist()
def run_default_risk_scoring():
    """
    Weekly scheduler job: rule-based scoring of installment plans
    for default risk. Assigns a risk_score (0-100) to each active plan.
    """
    active_plans = frappe.get_all(
        "Installment Plan",
        filters={"status": "Active"},
        fields=[
            "name",
            "buyer_profile",
            "total_outstanding",
            "overdue_amount",
            "total_penalties_accrued",
            "financed_amount",
            "plan_duration_months",
        ],
    )

    for plan_data in active_plans:
        risk_score = 0

        # Factor 1: Overdue ratio (0-40 points)
        if flt(plan_data.financed_amount) > 0:
            overdue_ratio = flt(plan_data.overdue_amount) / flt(plan_data.financed_amount)
            risk_score += min(40, int(overdue_ratio * 100))

        # Factor 2: Penalty accumulation (0-20 points)
        if flt(plan_data.total_outstanding) > 0:
            penalty_ratio = flt(plan_data.total_penalties_accrued) / flt(
                plan_data.total_outstanding
            )
            risk_score += min(20, int(penalty_ratio * 200))

        # Factor 3: Number of overdue installments (0-20 points)
        overdue_count = frappe.db.count(
            "Installment Schedule",
            {"parent": plan_data.name, "status": "Overdue"},
        )
        risk_score += min(20, overdue_count * 5)

        # Factor 4: Bounce history from linked PDCs (0-20 points)
        bounce_count = frappe.db.count(
            "Post Dated Cheque",
            {
                "installment_plan": plan_data.name,
                "status": "Bounced",
            },
        )
        risk_score += min(20, bounce_count * 10)

        risk_score = min(100, risk_score)

        # Store risk score on the plan
        frappe.db.set_value(
            "Installment Plan",
            plan_data.name,
            "risk_score",
            risk_score,
            update_modified=False,
        )

    frappe.db.commit()
    frappe.logger("realestate_eg").info(
        f"Default risk scoring complete: scored {len(active_plans)} plans"
    )
