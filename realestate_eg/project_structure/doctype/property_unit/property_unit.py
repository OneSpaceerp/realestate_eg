# Copyright (c) 2026, Nest Software Development and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt
from frappe.model.document import Document


class PropertyUnit(Document):
    """Controller for Property Unit — the core inventory item."""

    def validate(self):
        self._calculate_total_price()
        self._calculate_total_cost()
        self._validate_areas()

    def before_insert(self):
        if not self.unit_code:
            self._generate_unit_code()

    def on_update(self):
        if self.has_value_changed("status"):
            self._cascade_status_update()

    def _generate_unit_code(self):
        """Auto-generate unit_code from hierarchy: PROJECT-PHASE-ZONE-BLDG-UNIT."""
        parts = []
        if self.project:
            project_code = frappe.db.get_value(
                "Real Estate Project", self.project, "project_code"
            )
            parts.append(project_code or self.project[:6])

        if self.phase:
            parts.append(frappe.db.get_value("Project Phase", self.phase, "name")[:4] or "PH")
        if self.zone:
            parts.append(frappe.db.get_value("Project Zone", self.zone, "name")[:4] or "ZN")
        if self.building:
            parts.append(frappe.db.get_value("Building", self.building, "name")[:4] or "BL")

        # Add a sequential number
        existing_count = frappe.db.count(
            "Property Unit",
            {"project": self.project, "building": self.building or ""},
        )
        parts.append(str(existing_count + 1).zfill(3))

        self.unit_code = "-".join(parts)

    def _calculate_total_price(self):
        """
        Calculate total price based on area and pricing rules.
        Applies Unit Pricing Rules for floor, view, and finishing premiums.
        """
        base_price = flt(self.base_price_per_sqm) * flt(self.built_up_area_sqm)

        # Add garden and roof areas at reduced rates
        garden_price = flt(self.garden_area_sqm) * flt(self.base_price_per_sqm) * 0.5
        roof_price = flt(self.roof_area_sqm) * flt(self.base_price_per_sqm) * 0.3

        subtotal = base_price + garden_price + roof_price

        # Apply pricing rules if they exist
        pricing_rules = frappe.get_all(
            "Unit Pricing Rule",
            filters={"project": self.project, "unit_type": self.unit_type},
            fields=[
                "floor_premium_pct",
                "view_premium_pct",
                "finishing_premium",
                "cash_discount_pct",
                "early_bird_discount_pct",
                "validity_date",
            ],
            limit=1,
        )

        if pricing_rules:
            rule = pricing_rules[0]

            # Floor premium
            if self.floor_number and flt(rule.floor_premium_pct):
                floor_premium = subtotal * flt(rule.floor_premium_pct) / 100 * (self.floor_number or 0)
                subtotal += flt(floor_premium)

            # View premium
            if self.view_type and self.view_type in ("Sea", "Landmark", "Pool") and flt(rule.view_premium_pct):
                subtotal += subtotal * flt(rule.view_premium_pct) / 100

            # Finishing premium (flat amount)
            if flt(rule.finishing_premium):
                subtotal += flt(rule.finishing_premium)

        self.total_price = flt(subtotal, 2)

    def _calculate_total_cost(self):
        """Sum all allocated costs."""
        self.unit_total_cost = flt(
            flt(self.allocated_land_cost) + flt(self.allocated_infra_cost), 2
        )

    def _validate_areas(self):
        """Validate area values are positive."""
        if flt(self.gross_area_sqm) <= 0:
            frappe.throw(_("Gross Area must be greater than zero."))
        if flt(self.built_up_area_sqm) <= 0:
            frappe.throw(_("Built-Up Area must be greater than zero."))
        if flt(self.built_up_area_sqm) > flt(self.gross_area_sqm):
            frappe.throw(_("Built-Up Area cannot exceed Gross Area."))

    def _cascade_status_update(self):
        """Cascade status changes to related documents and dashboards."""
        if frappe.flags.in_import or frappe.flags.in_patch:
            return

        # Update project's total unit count
        if self.project:
            total = frappe.db.count("Property Unit", {"project": self.project})
            frappe.db.set_value(
                "Real Estate Project", self.project, "total_units", total,
                update_modified=False,
            )
