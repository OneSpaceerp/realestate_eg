# Copyright (c) 2026, Nest Software Development and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def after_install():
    """Run after app installation."""
    _create_custom_roles()
    _create_real_estate_settings()
    frappe.db.commit()
    frappe.msgprint(_("Real Estate Egypt app installed successfully!"))


def after_migrate():
    """Run after each migration."""
    _create_custom_roles()
    _create_real_estate_settings()
    frappe.db.commit()


def _create_custom_roles():
    """Create custom roles if they don't exist."""
    roles = [
        {"role_name": "Developer Admin", "desk_access": 1, "is_custom": 1},
        {"role_name": "Sales Manager", "desk_access": 1, "is_custom": 1},
        {"role_name": "Sales Agent", "desk_access": 1, "is_custom": 1},
        {"role_name": "Finance Manager", "desk_access": 1, "is_custom": 1},
        {"role_name": "Legal Counsel", "desk_access": 1, "is_custom": 1},
        {"role_name": "Property Manager", "desk_access": 1, "is_custom": 1},
        {"role_name": "Facility Manager", "desk_access": 1, "is_custom": 1},
    ]
    for role_data in roles:
        if not frappe.db.exists("Role", role_data["role_name"]):
            role = frappe.new_doc("Role")
            role.update(role_data)
            role.insert(ignore_permissions=True)


def _create_real_estate_settings():
    """Create Real Estate Settings singleton if it doesn't exist."""
    if not frappe.db.exists("DocType", "Real Estate Settings"):
        return
    if not frappe.db.exists("Real Estate Settings", "Real Estate Settings"):
        settings = frappe.new_doc("Real Estate Settings")
        settings.insert(ignore_permissions=True)
