# Copyright (c) 2026, Nest Software Development and contributors
# For license information, please see license.txt

"""
Cost Allocation Engine — Distributes land and infrastructure costs across units.

Methods:
  - By Area: Proportional to each unit's gross area (sqm)
  - By Market Value: Proportional to each unit's total selling price
  - Custom Weights: Manual weight assignment per unit
"""

import frappe
from frappe import _
from frappe.utils import flt


ALLOCATION_METHODS = ["By Area", "By Market Value", "Custom Weights"]


def allocate_costs(
    project_name: str,
    cost_type: str,
    total_cost: float,
    method: str = "By Area",
    custom_weights: dict = None,
) -> list[dict]:
    """
    Distribute a cost pool across all units in a project.

    Args:
        project_name: Real Estate Project name.
        cost_type: Type of cost being allocated (e.g., 'Land', 'Infrastructure').
        total_cost: Total cost amount to allocate.
        method: Allocation method (By Area, By Market Value, Custom Weights).
        custom_weights: Dict of {unit_name: weight} for Custom Weights method.

    Returns:
        List of dicts with unit_name and allocated_amount.
    """
    if method not in ALLOCATION_METHODS:
        frappe.throw(
            _("Invalid allocation method '{0}'. Use: {1}").format(
                method, ", ".join(ALLOCATION_METHODS)
            )
        )

    units = frappe.get_all(
        "Property Unit",
        filters={"project": project_name, "status": ["!=", "Cancelled"]},
        fields=["name", "gross_area_sqm", "total_price"],
    )

    if not units:
        frappe.throw(_("No units found for project {0}").format(project_name))

    allocations = []

    if method == "By Area":
        total_area = sum(flt(u.gross_area_sqm) for u in units)
        if total_area <= 0:
            frappe.throw(_("Total area is zero. Cannot allocate by area."))

        for unit in units:
            proportion = flt(unit.gross_area_sqm) / total_area
            allocated = flt(total_cost * proportion, 2)
            allocations.append(
                {
                    "unit_name": unit.name,
                    "proportion": flt(proportion, 6),
                    "allocated_amount": allocated,
                }
            )

    elif method == "By Market Value":
        total_value = sum(flt(u.total_price) for u in units)
        if total_value <= 0:
            frappe.throw(_("Total market value is zero. Cannot allocate by value."))

        for unit in units:
            proportion = flt(unit.total_price) / total_value
            allocated = flt(total_cost * proportion, 2)
            allocations.append(
                {
                    "unit_name": unit.name,
                    "proportion": flt(proportion, 6),
                    "allocated_amount": allocated,
                }
            )

    elif method == "Custom Weights":
        if not custom_weights:
            frappe.throw(_("Custom weights must be provided for Custom Weights method."))

        total_weight = sum(flt(w) for w in custom_weights.values())
        if total_weight <= 0:
            frappe.throw(_("Total custom weight is zero."))

        for unit in units:
            weight = flt(custom_weights.get(unit.name, 0))
            proportion = weight / total_weight
            allocated = flt(total_cost * proportion, 2)
            allocations.append(
                {
                    "unit_name": unit.name,
                    "proportion": flt(proportion, 6),
                    "allocated_amount": allocated,
                }
            )

    # Adjust rounding on last unit
    if allocations:
        total_allocated = sum(a["allocated_amount"] for a in allocations)
        rounding_diff = flt(total_cost - total_allocated, 2)
        if abs(rounding_diff) > 0:
            allocations[-1]["allocated_amount"] = flt(
                allocations[-1]["allocated_amount"] + rounding_diff, 2
            )

    return allocations


def apply_allocation_to_units(
    project_name: str,
    cost_type: str,
    total_cost: float,
    method: str = "By Area",
    custom_weights: dict = None,
):
    """
    Allocate costs and update the corresponding field on each Property Unit.

    Args:
        project_name: Real Estate Project name.
        cost_type: 'Land' or 'Infrastructure'.
        total_cost: Amount to allocate.
        method: Allocation method.
        custom_weights: Optional custom weights.
    """
    allocations = allocate_costs(
        project_name=project_name,
        cost_type=cost_type,
        total_cost=total_cost,
        method=method,
        custom_weights=custom_weights,
    )

    field_map = {
        "Land": "allocated_land_cost",
        "Infrastructure": "allocated_infra_cost",
    }

    field = field_map.get(cost_type)
    if not field:
        frappe.throw(
            _("Unknown cost type '{0}'. Use 'Land' or 'Infrastructure'.").format(cost_type)
        )

    for alloc in allocations:
        frappe.db.set_value(
            "Property Unit",
            alloc["unit_name"],
            field,
            alloc["allocated_amount"],
            update_modified=True,
        )

    # Update unit_total_cost on all affected units
    for alloc in allocations:
        unit = frappe.get_doc("Property Unit", alloc["unit_name"])
        unit.unit_total_cost = flt(unit.allocated_land_cost) + flt(unit.allocated_infra_cost)
        unit.db_set("unit_total_cost", unit.unit_total_cost, update_modified=True)

    frappe.db.commit()
    frappe.msgprint(
        _("Cost allocation applied: {0} EGP distributed across {1} units using '{2}' method.").format(
            frappe.utils.fmt_money(total_cost, currency="EGP"),
            len(allocations),
            method,
        )
    )

    return allocations


def calculate_unit_profitability(unit_name: str) -> dict:
    """
    Calculate profitability metrics for a single unit.

    Returns:
        Dict with revenue, costs, gross_margin, margin_pct.
    """
    unit = frappe.get_doc("Property Unit", unit_name)

    revenue = flt(unit.total_price, 2)
    total_cost = flt(unit.unit_total_cost, 2)
    gross_margin = flt(revenue - total_cost, 2)
    margin_pct = flt(gross_margin / revenue * 100, 2) if revenue > 0 else 0.0

    return {
        "unit_name": unit_name,
        "revenue": revenue,
        "allocated_land_cost": flt(unit.allocated_land_cost, 2),
        "allocated_infra_cost": flt(unit.allocated_infra_cost, 2),
        "total_cost": total_cost,
        "gross_margin": gross_margin,
        "margin_pct": margin_pct,
    }
