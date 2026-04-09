# Copyright (c) 2026, Nest Software Development and contributors
import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

class TestPropertyUnit(FrappeTestCase):
    def test_total_price_calculation(self):
        unit = frappe.new_doc("Property Unit")
        unit.unit_code = "TEST-001"
        unit.project = "TEST-PROJECT"
        unit.unit_type = "TEST-TYPE"
        unit.gross_area_sqm = 150
        unit.built_up_area_sqm = 120
        unit.base_price_per_sqm = 25000
        unit.finishing_level = "Fully Finished"
        unit.status = "Available"
        unit.validate()
        expected = 120 * 25000  # 3,000,000
        self.assertEqual(flt(unit.total_price, 2), flt(expected, 2))

    def test_area_validation(self):
        unit = frappe.new_doc("Property Unit")
        unit.unit_code = "TEST-002"
        unit.project = "TEST-PROJECT"
        unit.unit_type = "TEST-TYPE"
        unit.gross_area_sqm = 100
        unit.built_up_area_sqm = 150  # BUA > Gross — should fail
        unit.base_price_per_sqm = 25000
        unit.finishing_level = "Core & Shell"
        unit.status = "Available"
        self.assertRaises(frappe.ValidationError, unit.validate)
