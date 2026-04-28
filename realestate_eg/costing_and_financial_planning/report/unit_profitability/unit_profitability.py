# Copyright (c) 2026, Nest Software Development and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from realestate_eg.utils.cost_allocation import calculate_unit_profitability
from frappe.utils import flt

def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns()
    data = get_data(filters)

    return columns, data

def get_columns():
    return [
        {
            "fieldname": "unit_code",
            "label": _("Unit Code"),
            "fieldtype": "Link",
            "options": "Property Unit",
            "width": 150
        },
        {
            "fieldname": "project",
            "label": _("Project"),
            "fieldtype": "Link",
            "options": "Real Estate Project",
            "width": 120
        },
        {
            "fieldname": "status",
            "label": _("Status"),
            "fieldtype": "Data",
            "width": 100
        },
        {
            "fieldname": "revenue",
            "label": _("Total Revenue (Price)"),
            "fieldtype": "Currency",
            "options": "Company:company:default_currency",
            "width": 150
        },
        {
            "fieldname": "allocated_land_cost",
            "label": _("Land Cost"),
            "fieldtype": "Currency",
            "options": "Company:company:default_currency",
            "width": 120
        },
        {
            "fieldname": "allocated_infra_cost",
            "label": _("Infrastructure Cost"),
            "fieldtype": "Currency",
            "options": "Company:company:default_currency",
            "width": 130
        },
        {
            "fieldname": "total_cost",
            "label": _("Total Cost"),
            "fieldtype": "Currency",
            "options": "Company:company:default_currency",
            "width": 130
        },
        {
            "fieldname": "gross_margin",
            "label": _("Gross Margin (Profit)"),
            "fieldtype": "Currency",
            "options": "Company:company:default_currency",
            "width": 150
        },
        {
            "fieldname": "margin_pct",
            "label": _("Margin %"),
            "fieldtype": "Percent",
            "width": 100
        }
    ]

def get_data(filters):
    conditions = []
    
    if filters.get("project"):
        conditions.append(f"project = '{filters.get('project')}'")
    if filters.get("phase"):
        conditions.append(f"phase = '{filters.get('phase')}'")
    if filters.get("status"):
        conditions.append(f"status = '{filters.get('status')}'")
    else:
        # Default to sold/contracted units if no status is explicitly filtered
        conditions.append("status IN ('Under Contract', 'Sold', 'Delivered')")

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    units = frappe.db.sql(f"""
        SELECT name as unit_code, project, status
        FROM `tabProperty Unit`
        WHERE {where_clause}
    """, as_dict=True)

    data = []
    
    for u in units:
        profit_data = calculate_unit_profitability(u.unit_code)
        
        row = {
            "unit_code": u.unit_code,
            "project": u.project,
            "status": u.status,
            "revenue": profit_data.get("revenue"),
            "allocated_land_cost": profit_data.get("allocated_land_cost"),
            "allocated_infra_cost": profit_data.get("allocated_infra_cost"),
            "total_cost": profit_data.get("total_cost"),
            "gross_margin": profit_data.get("gross_margin"),
            "margin_pct": profit_data.get("margin_pct")
        }
        data.append(row)

    return data
