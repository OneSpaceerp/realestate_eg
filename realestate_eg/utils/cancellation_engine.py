# Copyright (c) 2026, Nest Software Development and contributors
# For license information, please see license.txt

"""
Cancellation Engine — Egyptian law-compliant deduction calculations.

Egyptian Real Estate Cancellation Deduction Rules:
  - Project completion < 60%:  Deduction = 10% of total paid
  - Project completion 60-80%: Deduction = 25% of total paid
  - Project completion > 80%:  Deduction = 40% of total paid
  - Developer delay (missed deadline + grace period): 0% deduction (100% refund)
  - Delivered units: Cannot be cancelled (redirect to Unit Transfer)
  
Reservation fee is non-refundable UNLESS cancellation is due to developer delay.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate, add_months, date_diff, cint


# Egyptian law tiered deduction percentages
DEDUCTION_TIERS = [
    {"min_pct": 0, "max_pct": 60, "deduction_pct": 10},
    {"min_pct": 60, "max_pct": 80, "deduction_pct": 25},
    {"min_pct": 80, "max_pct": 100, "deduction_pct": 40},
]


def calculate_deduction(
    total_amount_paid: float,
    project_completion_pct: float,
    is_developer_delay: bool = False,
    is_delivered: bool = False,
    reservation_fee: float = 0.0,
    executive_override_pct: float = None,
) -> dict:
    """
    Calculate cancellation deduction per Egyptian law.

    Args:
        total_amount_paid: Sum of all payments received from buyer.
        project_completion_pct: Current construction completion percentage.
        is_developer_delay: True if developer missed deadline + grace period.
        is_delivered: True if unit has been delivered to buyer.
        reservation_fee: Non-refundable reservation fee (unless developer delay).
        executive_override_pct: If set by executive, overrides the standard deduction.

    Returns:
        Dict with deduction_pct, deduction_amount, net_refund_amount, and breakdown.
    """
    result = {
        "total_amount_paid": flt(total_amount_paid, 2),
        "project_completion_pct": flt(project_completion_pct, 2),
        "is_developer_delay": is_developer_delay,
        "is_delivered": is_delivered,
        "reservation_fee": flt(reservation_fee, 2),
        "deduction_pct": 0.0,
        "deduction_amount": 0.0,
        "reservation_fee_refundable": False,
        "net_refund_amount": 0.0,
        "deduction_reason": "",
    }

    # Delivered units cannot be cancelled
    if is_delivered:
        frappe.throw(
            _(
                "Delivered units cannot be cancelled. "
                "Please use the Unit Transfer workflow instead."
            )
        )

    # Developer delay → 100% refund including reservation fee
    if is_developer_delay:
        result["deduction_pct"] = 0.0
        result["deduction_amount"] = 0.0
        result["reservation_fee_refundable"] = True
        result["net_refund_amount"] = flt(total_amount_paid, 2)
        result["deduction_reason"] = _(
            "Developer delay: Developer missed delivery deadline plus grace period. "
            "Full refund as per Egyptian law."
        )
        return result

    # Executive override
    if executive_override_pct is not None:
        deduction_pct = flt(executive_override_pct, 2)
        result["deduction_reason"] = _(
            "Executive override: deduction manually set to {0}%"
        ).format(deduction_pct)
    else:
        # Standard tiered deduction
        completion = flt(project_completion_pct)
        deduction_pct = 10.0  # Default

        for tier in DEDUCTION_TIERS:
            if tier["min_pct"] <= completion < tier["max_pct"]:
                deduction_pct = tier["deduction_pct"]
                break
        else:
            # completion >= 100
            deduction_pct = 40.0

        result["deduction_reason"] = _(
            "Standard deduction: project at {0}% completion → {1}% deduction tier"
        ).format(completion, deduction_pct)

    result["deduction_pct"] = deduction_pct
    result["deduction_amount"] = flt(
        flt(total_amount_paid) * deduction_pct / 100, 2
    )

    # Reservation fee is non-refundable in standard cancellation
    result["reservation_fee_refundable"] = False
    result["net_refund_amount"] = flt(
        flt(total_amount_paid) - result["deduction_amount"], 2
    )

    return result


def check_developer_delay(
    project_name: str,
    contracted_delivery_date: str,
    grace_period_months: int = 6,
) -> bool:
    """
    Check if the developer has exceeded the delivery deadline + grace period.

    Args:
        project_name: Name of the Real Estate Project.
        contracted_delivery_date: Contractual delivery date.
        grace_period_months: Grace period beyond the delivery date.

    Returns:
        True if current date exceeds delivery_date + grace_period.
    """
    today = getdate(nowdate())
    delivery = getdate(contracted_delivery_date)
    grace_deadline = add_months(delivery, cint(grace_period_months))

    # Also check if unit is delivered
    project = frappe.get_doc("Real Estate Project", project_name)
    if project.status == "Fully Delivered":
        return False

    return today > getdate(grace_deadline)


def process_cancellation(cancellation_name: str):
    """
    Execute the full cancellation workflow:
    1. Void remaining installment schedule rows
    2. Return un-cleared PDCs to buyer
    3. Generate Refund Schedule
    4. Trigger Commission Clawback if applicable
    5. Update Property Unit status to 'Available'
    6. Push unit back to CRM as available inventory

    Args:
        cancellation_name: Name of the Unit Cancellation document.
    """
    cancellation = frappe.get_doc("Unit Cancellation", cancellation_name)

    if cancellation.status != "Approved":
        frappe.throw(_("Cancellation must be approved before processing."))

    # 1. Void remaining installment schedule rows
    _void_installment_schedule(cancellation)

    # 2. Return un-cleared PDCs
    _return_pdcs_to_buyer(cancellation)

    # 3. Generate Refund Schedule
    _generate_refund_schedule(cancellation)

    # 4. Trigger Commission Clawback
    _process_commission_clawback(cancellation)

    # 5. Update Property Unit status
    frappe.db.set_value(
        "Property Unit",
        cancellation.property_unit,
        {
            "status": "Available",
            "current_buyer": None,
            "installment_plan": None,
        },
    )

    # 6. Update contract status
    frappe.db.set_value(
        "Property Contract",
        cancellation.property_contract,
        "status",
        "Cancelled",
    )

    # Update cancellation status
    cancellation.status = "Refund in Progress"
    cancellation.save(ignore_permissions=True)

    frappe.db.commit()
    frappe.msgprint(
        _("Cancellation processed. Refund schedule generated for {0} EGP.").format(
            frappe.utils.fmt_money(cancellation.net_refund_amount, currency="EGP")
        )
    )


def _void_installment_schedule(cancellation):
    """Void all unpaid installment rows and close the plan."""
    contract = frappe.get_doc("Property Contract", cancellation.property_contract)
    if contract.installment_plan:
        plan = frappe.get_doc("Installment Plan", contract.installment_plan)
        for row in plan.schedule:
            if row.status not in ("Paid",):
                row.status = "Waived"
                row.balance = 0
        plan.status = "Cancelled"
        plan.flags.ignore_validate = True
        plan.save(ignore_permissions=True)


def _return_pdcs_to_buyer(cancellation):
    """Return all un-cleared PDCs linked to the cancelled contract."""
    contract = frappe.get_doc("Property Contract", cancellation.property_contract)
    if not contract.installment_plan:
        return

    pdcs = frappe.get_all(
        "Post Dated Cheque",
        filters={
            "installment_plan": contract.installment_plan,
            "status": ["in", ["Received", "In Vault"]],
        },
        fields=["name"],
    )

    for pdc_data in pdcs:
        frappe.db.set_value(
            "Post Dated Cheque",
            pdc_data.name,
            {
                "status": "Returned to Buyer",
                "physical_location": "Returned to Buyer",
            },
        )


def _generate_refund_schedule(cancellation):
    """Create a Refund Schedule document with equal monthly payments."""
    if flt(cancellation.net_refund_amount) <= 0:
        return

    # Default 12-month refund period
    duration_months = 12
    if cancellation.refund_method == "Lump Sum":
        duration_months = 1
    elif cancellation.refund_method == "Conditional on Resale":
        duration_months = 0  # Will be triggered on resale

    if duration_months > 0:
        refund_schedule = frappe.new_doc("Refund Schedule")
        refund_schedule.unit_cancellation = cancellation.name
        refund_schedule.net_refund_amount = cancellation.net_refund_amount
        refund_schedule.refund_method = cancellation.refund_method
        refund_schedule.duration_months = duration_months

        monthly_amount = flt(cancellation.net_refund_amount / duration_months, 2)
        current_date = getdate(nowdate())

        for i in range(duration_months):
            from dateutil.relativedelta import relativedelta

            due_date = current_date + relativedelta(months=i + 1)
            amount = monthly_amount
            if i == duration_months - 1:
                # Last row absorbs rounding
                amount = flt(
                    cancellation.net_refund_amount - (monthly_amount * (duration_months - 1)),
                    2,
                )

            refund_schedule.append(
                "schedule",
                {
                    "installment_number": i + 1,
                    "due_date": due_date,
                    "amount": amount,
                    "status": "Pending",
                },
            )

        refund_schedule.insert(ignore_permissions=True)
        cancellation.refund_schedule = refund_schedule.name


def _process_commission_clawback(cancellation):
    """Create Commission Clawback if broker commission exists with vesting conditions."""
    if not cancellation.broker_clawback_required:
        return

    # Find broker commissions linked to the property contract
    commissions = frappe.get_all(
        "Broker Commission",
        filters={
            "property_contract": cancellation.property_contract,
            "payment_status": ["in", ["Pending", "Partially Paid", "Paid"]],
        },
        fields=["name", "commission_amount", "commission_type"],
    )

    for comm in commissions:
        if comm.commission_type in ("Collection-Based", "Delivery-Based"):
            clawback = frappe.new_doc("Commission Clawback")
            clawback.unit_cancellation = cancellation.name
            clawback.broker_commission = comm.name
            clawback.original_commission_amount = comm.commission_amount
            clawback.clawback_amount = comm.commission_amount
            clawback.clawback_method = "Debit Memo"
            clawback.reason = _(
                "Unit cancellation: {0}. Commission clawback required per vesting conditions."
            ).format(cancellation.name)
            clawback.status = "Pending"
            clawback.insert(ignore_permissions=True)

            # Update original commission
            frappe.db.set_value(
                "Broker Commission",
                comm.name,
                {
                    "payment_status": "Clawback",
                    "clawback_amount": comm.commission_amount,
                    "clawback_reason": f"Unit cancelled: {cancellation.name}",
                },
            )
