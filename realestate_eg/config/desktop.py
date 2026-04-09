# Copyright (c) 2026, Nest Software Development and contributors
# For license information, please see license.txt

from frappe import _


def get_data():
    """Return module cards for the Desk sidebar."""
    return [
        {
            "module_name": "Land and Project Development",
            "color": "#4CAF50",
            "icon": "octicon octicon-globe",
            "type": "module",
            "label": _("Land & Project Development"),
            "description": _("Land acquisition, NUCA compliance, project lifecycle"),
        },
        {
            "module_name": "Project Structure",
            "color": "#2196F3",
            "icon": "octicon octicon-organization",
            "type": "module",
            "label": _("Project Structure"),
            "description": _("Hierarchy, units, GIS, inventory status"),
        },
        {
            "module_name": "Costing and Financial Planning",
            "color": "#FF9800",
            "icon": "octicon octicon-graph",
            "type": "module",
            "label": _("Costing & Financial Planning"),
            "description": _("BOQ, job costing, cost allocation, dynamic pricing"),
        },
        {
            "module_name": "Construction Management",
            "color": "#795548",
            "icon": "octicon octicon-tools",
            "type": "module",
            "label": _("Construction Management"),
            "description": _("Progress tracking, milestones, escrow, BIM"),
        },
        {
            "module_name": "CRM and Sales",
            "color": "#E91E63",
            "icon": "octicon octicon-megaphone",
            "type": "module",
            "label": _("CRM & Sales"),
            "description": _("Leads, AI matching, quotations, pipeline"),
        },
        {
            "module_name": "Contract Management",
            "color": "#9C27B0",
            "icon": "octicon octicon-law",
            "type": "module",
            "label": _("Contract Management"),
            "description": _("Contract generation, digital signatures, clauses"),
        },
        {
            "module_name": "Installment Management",
            "color": "#00BCD4",
            "icon": "octicon octicon-credit-card",
            "type": "module",
            "label": _("Installment Management"),
            "description": _("Payment plans, amortization, penalties, restructuring"),
        },
        {
            "module_name": "PDC Management",
            "color": "#607D8B",
            "icon": "octicon octicon-note",
            "type": "module",
            "label": _("PDC Management"),
            "description": _("Cheque lifecycle, OCR, banking, clearing"),
        },
        {
            "module_name": "Cancellation and Refund",
            "color": "#F44336",
            "icon": "octicon octicon-x",
            "type": "module",
            "label": _("Cancellation & Refund"),
            "description": _("Returns, deductions, refund scheduling, clawbacks"),
        },
        {
            "module_name": "Property and Rental",
            "color": "#3F51B5",
            "icon": "octicon octicon-home",
            "type": "module",
            "label": _("Property & Rental"),
            "description": _("Leasing, tenant management, 2025 law compliance"),
        },
        {
            "module_name": "Facility Management",
            "color": "#009688",
            "icon": "octicon octicon-gear",
            "type": "module",
            "label": _("Facility Management"),
            "description": _("Maintenance, Wadeea, IoT, ticketing"),
        },
        {
            "module_name": "Tax and Compliance",
            "color": "#FF5722",
            "icon": "octicon octicon-checklist",
            "type": "module",
            "label": _("Tax & Compliance"),
            "description": _("ETA e-invoicing, e-receipts, FX compliance"),
        },
    ]
