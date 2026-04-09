# Copyright (c) 2026, Nest Software Development and contributors
# For license information, please see license.txt

"""
Installment Calculator — Core schedule generation engine.

Handles:
- Monthly, Quarterly, Semi-Annual, Annual installment schedule generation
- Admin fee / interest markup (hidden from buyer)
- Balloon payment support
- Restructuring (voiding old schedule and regenerating)
- Collection forecast projection
"""

import frappe
from frappe import _
from frappe.utils import (
    add_months,
    flt,
    getdate,
    nowdate,
    date_diff,
    cint,
    fmt_money,
)
from datetime import date
from dateutil.relativedelta import relativedelta


FREQUENCY_MONTHS = {
    "Monthly": 1,
    "Quarterly": 3,
    "Semi-Annual": 6,
    "Annual": 12,
}


def generate_installment_schedule(
    financed_amount: float,
    start_date: str,
    duration_months: int,
    frequency: str = "Monthly",
    admin_fee_pct: float = 0.0,
    balloon_amount: float = 0.0,
    late_penalty_rate: float = 0.0,
) -> list[dict]:
    """
    Generate a list of installment schedule rows.

    Args:
        financed_amount: Total amount to be financed (after reservation + downpayment).
        start_date: Date of the first installment.
        duration_months: Total plan duration in months.
        frequency: Payment frequency (Monthly, Quarterly, Semi-Annual, Annual).
        admin_fee_pct: Hidden admin/interest markup percentage.
        balloon_amount: If set, the last installment equals this amount.
        late_penalty_rate: Penalty rate per month for overdue (stored for reference).

    Returns:
        List of dicts with keys: idx, due_date, amount, penalty_amount, total_due,
        paid_amount, balance, status
    """
    if frequency not in FREQUENCY_MONTHS:
        frappe.throw(
            _("Invalid frequency '{0}'. Must be one of: {1}").format(
                frequency, ", ".join(FREQUENCY_MONTHS.keys())
            )
        )

    interval_months = FREQUENCY_MONTHS[frequency]
    total_installments = max(1, duration_months // interval_months)

    # Apply admin fee markup to the total
    total_with_markup = flt(financed_amount) * (1 + flt(admin_fee_pct) / 100)

    schedule = []
    current_date = getdate(start_date)

    if balloon_amount > 0 and total_installments > 1:
        # Balloon payment: last installment is fixed, rest are equal
        remaining = total_with_markup - flt(balloon_amount)
        regular_amount = flt(remaining / (total_installments - 1), 2)
    else:
        regular_amount = flt(total_with_markup / total_installments, 2)
        balloon_amount = 0.0

    running_total = 0.0

    for i in range(1, total_installments + 1):
        if i == total_installments:
            # Last installment absorbs rounding differences
            if balloon_amount > 0:
                amount = flt(balloon_amount, 2)
            else:
                amount = flt(total_with_markup - running_total, 2)
        else:
            amount = regular_amount

        running_total += amount

        schedule.append(
            {
                "idx": i,
                "due_date": current_date,
                "amount": amount,
                "penalty_amount": 0.0,
                "total_due": amount,
                "paid_amount": 0.0,
                "balance": amount,
                "payment_date": None,
                "payment_entry": None,
                "pdc": None,
                "status": "Upcoming",
                "days_overdue": 0,
            }
        )

        current_date = current_date + relativedelta(months=interval_months)

    return schedule


def calculate_early_settlement_amount(
    outstanding_balance: float,
    discount_pct: float = 0.0,
) -> dict:
    """
    Calculate amount due for early plan settlement.

    Args:
        outstanding_balance: Sum of all unpaid installments.
        discount_pct: Discount percentage for early settlement.

    Returns:
        Dict with settlement_amount and discount_amount.
    """
    discount_amount = flt(outstanding_balance * flt(discount_pct) / 100, 2)
    settlement_amount = flt(outstanding_balance - discount_amount, 2)

    return {
        "outstanding_balance": flt(outstanding_balance, 2),
        "discount_pct": flt(discount_pct, 2),
        "discount_amount": discount_amount,
        "settlement_amount": settlement_amount,
    }


def recalculate_schedule_after_restructuring(
    plan_name: str,
    restructuring_type: str,
    effective_date: str,
    new_duration_months: int = 0,
    balloon_amount: float = 0.0,
    new_installment_amount: float = 0.0,
) -> list[dict]:
    """
    Void remaining unpaid schedule rows and generate new ones.

    Args:
        plan_name: Name of the Installment Plan.
        restructuring_type: One of Balloon Payment, Term Extension, Payment Reduction, Full Reschedule.
        effective_date: Date from which the new schedule begins.
        new_duration_months: If extending term, new duration from effective_date.
        balloon_amount: If balloon payment restructuring.
        new_installment_amount: If payment reduction.

    Returns:
        List of new schedule rows.
    """
    plan = frappe.get_doc("Installment Plan", plan_name)

    # Calculate outstanding amount from unpaid installments
    outstanding = 0.0
    for row in plan.schedule:
        if row.status not in ("Paid",):
            outstanding += flt(row.balance)

    if outstanding <= 0:
        frappe.throw(_("No outstanding balance to restructure."))

    frequency = plan.frequency
    interval_months = FREQUENCY_MONTHS.get(frequency, 1)

    if restructuring_type == "Balloon Payment":
        remaining_installments = max(1, cint(new_duration_months / interval_months))
        return generate_installment_schedule(
            financed_amount=outstanding,
            start_date=effective_date,
            duration_months=new_duration_months or (remaining_installments * interval_months),
            frequency=frequency,
            balloon_amount=flt(balloon_amount),
        )

    elif restructuring_type == "Term Extension":
        return generate_installment_schedule(
            financed_amount=outstanding,
            start_date=effective_date,
            duration_months=cint(new_duration_months),
            frequency=frequency,
        )

    elif restructuring_type == "Payment Reduction":
        if flt(new_installment_amount) <= 0:
            frappe.throw(_("New installment amount must be greater than zero."))
        new_total_installments = max(1, int(outstanding / flt(new_installment_amount)))
        new_duration = new_total_installments * interval_months
        return generate_installment_schedule(
            financed_amount=outstanding,
            start_date=effective_date,
            duration_months=new_duration,
            frequency=frequency,
        )

    elif restructuring_type == "Full Reschedule":
        return generate_installment_schedule(
            financed_amount=outstanding,
            start_date=effective_date,
            duration_months=cint(new_duration_months),
            frequency=frequency,
            balloon_amount=flt(balloon_amount),
        )

    else:
        frappe.throw(_("Unknown restructuring type: {0}").format(restructuring_type))


@frappe.whitelist()
def generate_collection_forecast():
    """
    Weekly scheduler job: project cash inflows from installments and PDCs
    over the next 12 months for reporting.
    """
    today = getdate(nowdate())
    forecast_end = today + relativedelta(months=12)

    # Get all unpaid installment schedule rows with future due dates
    upcoming = frappe.db.sql(
        """
        SELECT
            ip.name AS plan_name,
            ip.property_unit,
            ip.buyer_profile,
            isc.due_date,
            isc.amount,
            isc.balance,
            isc.status
        FROM `tabInstallment Schedule` isc
        JOIN `tabInstallment Plan` ip ON isc.parent = ip.name
        WHERE isc.status IN ('Upcoming', 'Due', 'Overdue', 'Partially Paid')
            AND isc.due_date BETWEEN %s AND %s
            AND ip.status = 'Active'
        ORDER BY isc.due_date
        """,
        (today, forecast_end),
        as_dict=True,
    )

    # Group by month for forecast
    monthly_forecast = {}
    for row in upcoming:
        month_key = getdate(row.due_date).strftime("%Y-%m")
        if month_key not in monthly_forecast:
            monthly_forecast[month_key] = {
                "month": month_key,
                "expected_amount": 0.0,
                "overdue_amount": 0.0,
                "installment_count": 0,
            }
        monthly_forecast[month_key]["expected_amount"] += flt(row.balance)
        monthly_forecast[month_key]["installment_count"] += 1
        if row.status == "Overdue":
            monthly_forecast[month_key]["overdue_amount"] += flt(row.balance)

    # Store as a cached singleton for the Collection Forecast report
    cache_key = "realestate_eg:collection_forecast"
    frappe.cache.set_value(
        cache_key,
        {
            "generated_at": nowdate(),
            "forecast": list(monthly_forecast.values()),
        },
        expires_in_sec=7 * 24 * 3600,  # 7 days
    )

    frappe.logger("realestate_eg").info(
        f"Collection forecast generated: {len(upcoming)} installments projected over 12 months"
    )


def get_plan_summary(plan_name: str) -> dict:
    """
    Get a comprehensive summary of an installment plan.

    Args:
        plan_name: Name of the Installment Plan.

    Returns:
        Dict with totals, counts, and status breakdown.
    """
    plan = frappe.get_doc("Installment Plan", plan_name)

    total_scheduled = 0.0
    total_paid = 0.0
    total_overdue = 0.0
    total_penalties = 0.0
    count_paid = 0
    count_overdue = 0
    count_upcoming = 0

    for row in plan.schedule:
        total_scheduled += flt(row.amount)
        total_paid += flt(row.paid_amount)
        total_penalties += flt(row.penalty_amount)

        if row.status == "Paid":
            count_paid += 1
        elif row.status == "Overdue":
            count_overdue += 1
            total_overdue += flt(row.balance)
        else:
            count_upcoming += 1

    return {
        "plan_name": plan_name,
        "total_installments": len(plan.schedule),
        "total_scheduled": flt(total_scheduled, 2),
        "total_paid": flt(total_paid, 2),
        "total_outstanding": flt(total_scheduled - total_paid, 2),
        "total_overdue": flt(total_overdue, 2),
        "total_penalties": flt(total_penalties, 2),
        "count_paid": count_paid,
        "count_overdue": count_overdue,
        "count_upcoming": count_upcoming,
        "completion_pct": flt(total_paid / total_scheduled * 100, 2) if total_scheduled else 0.0,
    }
