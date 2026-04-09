# Copyright (c) 2026, Nest Software Development and contributors
# For license information, please see license.txt

"""
Rental Law Engine — 2025 Egyptian Rental Law compliance.

Key rules:
  - Old Rent Transition: Multiplier applied to base old rent amount
    - Prime areas: 20× multiplier
    - Medium-income areas: 10× multiplier
    - Lower-income areas: 10× multiplier
  - Minimum rents: Prime = EGP 1000, Medium = EGP 400, Lower = EGP 250
  - Transitional period: 7 years for residential, 5 years for commercial
  - Annual increase during transition: Tracked per area classification
  
Notifications:
  - 6 months before transitional_end_date: first warning
  - 3 months before: second warning
  - 1 month before: final notice
"""

import frappe
from frappe import _
from frappe.utils import (
    add_months,
    add_days,
    date_diff,
    flt,
    getdate,
    nowdate,
    cint,
)


# 2025 Rental Law multipliers by area classification
OLD_RENT_CONFIG = {
    "Prime": {"multiplier": 20, "minimum_rent": 1000},
    "Medium-Income": {"multiplier": 10, "minimum_rent": 400},
    "Lower-Income": {"multiplier": 10, "minimum_rent": 250},
    "Commercial": {"multiplier": 10, "minimum_rent": 1000},
}

# Transitional period by property type
TRANSITIONAL_PERIODS = {
    "Residential": 7,  # years
    "Commercial": 5,   # years
}

# Notification thresholds (months before transitional end)
NOTIFICATION_THRESHOLDS = [6, 3, 1]


def calculate_new_rent(
    old_rent_base_amount: float,
    area_classification: str,
) -> dict:
    """
    Calculate new rent amount under 2025 Rental Law.

    The new rent is the HIGHER of:
      - old_rent_base × multiplier
      - minimum rent for the area

    Args:
        old_rent_base_amount: Original monthly rent under old law.
        area_classification: Prime, Medium-Income, Lower-Income, or Commercial.

    Returns:
        Dict with calculated values.
    """
    config = OLD_RENT_CONFIG.get(area_classification)
    if not config:
        frappe.throw(
            _("Unknown area classification: {0}. Must be: {1}").format(
                area_classification, ", ".join(OLD_RENT_CONFIG.keys())
            )
        )

    multiplied_rent = flt(old_rent_base_amount * config["multiplier"], 2)
    minimum_rent = flt(config["minimum_rent"], 2)
    effective_rent = max(multiplied_rent, minimum_rent)

    return {
        "old_rent_base_amount": flt(old_rent_base_amount, 2),
        "area_classification": area_classification,
        "multiplier": config["multiplier"],
        "multiplied_rent": multiplied_rent,
        "minimum_rent": minimum_rent,
        "effective_rent": effective_rent,
        "increase_amount": flt(effective_rent - old_rent_base_amount, 2),
        "increase_pct": flt(
            (effective_rent - old_rent_base_amount) / old_rent_base_amount * 100, 2
        )
        if old_rent_base_amount > 0
        else 0,
    }


def calculate_transitional_end_date(
    lease_start_date: str,
    property_type: str = "Residential",
) -> str:
    """
    Calculate the transitional end date based on the 2025 law.

    Args:
        lease_start_date: When the transitional lease started.
        property_type: Residential (7 years) or Commercial (5 years).

    Returns:
        End date as string.
    """
    years = TRANSITIONAL_PERIODS.get(property_type, 7)
    return add_months(getdate(lease_start_date), years * 12)


@frappe.whitelist()
def check_lease_expirations():
    """
    Daily scheduler job: check all active leases for upcoming expirations
    and trigger notifications per the defined thresholds.

    This job is idempotent.
    """
    today = getdate(nowdate())

    active_leases = frappe.get_all(
        "Lease Contract",
        filters={"status": ["in", ["Active", "Expiring Soon"]]},
        fields=[
            "name",
            "property_unit",
            "tenant",
            "lease_type",
            "end_date",
            "transitional_end_date",
            "area_classification",
            "monthly_rent",
            "auto_renewal",
        ],
    )

    for lease in active_leases:
        # Determine the relevant expiry date
        if lease.lease_type in ("Old Rent", "Transitional") and lease.transitional_end_date:
            expiry_date = getdate(lease.transitional_end_date)
        else:
            expiry_date = getdate(lease.end_date)

        days_until_expiry = date_diff(expiry_date, today)

        # Update status if approaching expiry
        if 0 < days_until_expiry <= 90 and lease.status != "Expiring Soon":
            frappe.db.set_value(
                "Lease Contract", lease.name, "status", "Expiring Soon"
            )

        if days_until_expiry <= 0:
            if lease.auto_renewal:
                _process_auto_renewal(lease)
            else:
                frappe.db.set_value(
                    "Lease Contract", lease.name, "status", "Expired"
                )
            continue

        # Send notifications at thresholds
        for months_before in NOTIFICATION_THRESHOLDS:
            threshold_date = add_months(expiry_date, -months_before)
            if getdate(threshold_date) <= today:
                _send_lease_expiry_notification(
                    lease, months_before, days_until_expiry
                )

    frappe.db.commit()
    frappe.logger("realestate_eg").info(
        f"Lease expiration check: processed {len(active_leases)} active leases"
    )


def _send_lease_expiry_notification(lease: dict, months_before: int, days_remaining: int):
    """Send lease expiry notification to property manager."""
    # Deduplicate: check if notification already sent
    flag_key = f"lease_expiry_{lease.name}_{months_before}m"
    already_sent = frappe.db.exists(
        "Comment",
        {
            "reference_doctype": "Lease Contract",
            "reference_name": lease.name,
            "content": ["like", f"%{flag_key}%"],
        },
    )
    if already_sent:
        return

    # Notify property managers
    property_managers = frappe.get_all(
        "Has Role",
        filters={"role": "Property Manager", "parenttype": "User"},
        fields=["parent"],
    )

    for pm in property_managers:
        frappe.get_doc(
            {
                "doctype": "ToDo",
                "description": _(
                    "Lease expiry alert: Lease {0} for unit {1} (tenant: {2}) "
                    "expires in {3} days ({4} months). "
                    "Lease type: {5}. Monthly rent: {6} EGP."
                ).format(
                    lease.name,
                    lease.property_unit,
                    lease.tenant,
                    days_remaining,
                    months_before,
                    lease.lease_type,
                    frappe.utils.fmt_money(lease.monthly_rent, currency="EGP"),
                ),
                "reference_type": "Lease Contract",
                "reference_name": lease.name,
                "assigned_by": "Administrator",
                "allocated_to": pm.parent,
                "priority": "High" if months_before <= 1 else "Medium",
                "status": "Open",
            }
        ).insert(ignore_permissions=True)

    # Log notification
    frappe.get_doc(
        {
            "doctype": "Comment",
            "comment_type": "Info",
            "reference_doctype": "Lease Contract",
            "reference_name": lease.name,
            "content": _("Lease expiry notification sent ({0} months before) — {1}").format(
                months_before, flag_key
            ),
        }
    ).insert(ignore_permissions=True)

    # Send email to tenant if applicable
    try:
        tenant = frappe.get_doc("Tenant", lease.tenant)
        if tenant.email:
            frappe.sendmail(
                recipients=[tenant.email],
                subject=_("Lease Expiry Notice — {0}").format(lease.property_unit),
                template="lease_expiry_alert",
                args={
                    "tenant_name": tenant.tenant_name,
                    "property_unit": lease.property_unit,
                    "expiry_date": frappe.utils.format_date(lease.end_date),
                    "days_remaining": days_remaining,
                    "monthly_rent": frappe.utils.fmt_money(
                        lease.monthly_rent, currency="EGP"
                    ),
                    "lease_type": lease.lease_type,
                },
                now=True,
            )
    except Exception as e:
        frappe.logger("realestate_eg").warning(
            f"Failed to send lease expiry email for {lease.name}: {e}"
        )


def _process_auto_renewal(lease: dict):
    """Auto-renew a lease that has the auto_renewal flag set."""
    lease_doc = frappe.get_doc("Lease Contract", lease.name)

    new_start = getdate(lease_doc.end_date)
    new_end = add_months(new_start, 12)  # Renew for 1 year

    # Apply annual increase if applicable
    new_rent = flt(lease_doc.monthly_rent)
    if flt(lease_doc.annual_increase_pct) > 0:
        new_rent = flt(
            new_rent * (1 + flt(lease_doc.annual_increase_pct) / 100), 2
        )

    lease_doc.start_date = new_start
    lease_doc.end_date = new_end
    lease_doc.monthly_rent = new_rent
    lease_doc.status = "Active"
    lease_doc.flags.ignore_validate = True
    lease_doc.save(ignore_permissions=True)

    frappe.logger("realestate_eg").info(
        f"Lease {lease.name} auto-renewed: {new_start} to {new_end}, rent: {new_rent} EGP"
    )


@frappe.whitelist()
def process_old_rent_transitions():
    """
    Monthly scheduler job: recalculate rent for Old Rent and Transitional leases
    on their anniversary dates.
    """
    today = getdate(nowdate())

    transitional_leases = frappe.get_all(
        "Lease Contract",
        filters={
            "lease_type": ["in", ["Old Rent", "Transitional"]],
            "status": ["in", ["Active", "Expiring Soon"]],
        },
        fields=[
            "name",
            "old_rent_base_amount",
            "area_classification",
            "start_date",
            "monthly_rent",
        ],
    )

    for lease in transitional_leases:
        if not lease.old_rent_base_amount or not lease.area_classification:
            continue

        start = getdate(lease.start_date)
        # Check if today is an anniversary month
        if start.month == today.month and start.day == today.day:
            new_rent_data = calculate_new_rent(
                old_rent_base_amount=flt(lease.old_rent_base_amount),
                area_classification=lease.area_classification,
            )

            if flt(new_rent_data["effective_rent"]) != flt(lease.monthly_rent):
                frappe.db.set_value(
                    "Lease Contract",
                    lease.name,
                    {
                        "monthly_rent": new_rent_data["effective_rent"],
                        "old_rent_multiplier": new_rent_data["multiplier"],
                        "old_rent_minimum": new_rent_data["minimum_rent"],
                    },
                )

                frappe.logger("realestate_eg").info(
                    f"Old rent transition for {lease.name}: "
                    f"{lease.monthly_rent} → {new_rent_data['effective_rent']} EGP"
                )

    frappe.db.commit()
