# Copyright (c) 2026, Nest Software Development and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt


class TestLandParcel(FrappeTestCase):
    """Test cases for Land Parcel DocType."""

    def test_transfer_tax_calculation(self):
        """Test that transfer tax is auto-calculated at 2.5%."""
        parcel = frappe.new_doc("Land Parcel")
        parcel.parcel_name = "Test Parcel"
        parcel.location = "New Cairo"
        parcel.governorate = "Cairo"
        parcel.total_area_sqm = 10000
        parcel.acquisition_type = "Private Purchase"
        parcel.acquisition_date = "2026-01-01"
        parcel.total_cost = 50000000  # 50M EGP
        parcel.status = "Under Negotiation"
        parcel.validate()

        self.assertEqual(flt(parcel.transfer_tax_amount, 2), 1250000.00)

    def test_zero_area_validation(self):
        """Test that zero area raises an error."""
        parcel = frappe.new_doc("Land Parcel")
        parcel.parcel_name = "Test Parcel"
        parcel.location = "New Cairo"
        parcel.governorate = "Cairo"
        parcel.total_area_sqm = 0
        parcel.acquisition_type = "Private Purchase"
        parcel.acquisition_date = "2026-01-01"
        parcel.total_cost = 50000000
        parcel.status = "Under Negotiation"

        self.assertRaises(frappe.ValidationError, parcel.validate)

    def test_transfer_tax_rate(self):
        """Test transfer tax at exactly 2.5%."""
        parcel = frappe.new_doc("Land Parcel")
        parcel.parcel_name = "Rate Test"
        parcel.location = "6th October"
        parcel.governorate = "Giza"
        parcel.total_area_sqm = 5000
        parcel.acquisition_type = "Government Tender"
        parcel.acquisition_date = "2026-06-15"
        parcel.total_cost = 20000000  # 20M EGP
        parcel.status = "Acquired"
        parcel.validate()

        expected_tax = 20000000 * 0.025  # 500,000 EGP
        self.assertEqual(flt(parcel.transfer_tax_amount, 2), flt(expected_tax, 2))
