from . import __version__ as app_version

app_name = "realestate_eg"
app_title = "Real Estate Egypt"
app_publisher = "Nest Software Development"
app_description = "Comprehensive Real Estate & Installment Management for the Egyptian Market"
app_email = "info@nsd-eg.com"
app_license = "MIT"
required_apps = ["frappe", "erpnext"]

# --------------------------------------------------------------------------
# Includes in <head>
# --------------------------------------------------------------------------
app_include_js = ["/assets/realestate_eg/js/realestate_eg.js"]
app_include_css = ["/assets/realestate_eg/css/realestate_eg.css"]

# --------------------------------------------------------------------------
# DocType Class Overrides
# --------------------------------------------------------------------------
override_doctype_class = {
    "Sales Invoice": "realestate_eg.overrides.sales_invoice.CustomSalesInvoice",
    "Customer": "realestate_eg.overrides.customer.CustomCustomer",
    "Payment Entry": "realestate_eg.overrides.payment_entry.CustomPaymentEntry",
}

# --------------------------------------------------------------------------
# Document Events
# --------------------------------------------------------------------------
doc_events = {
    "Property Contract": {
        "on_submit": "realestate_eg.contract_management.doctype.property_contract.property_contract.on_contract_submit",
        "on_cancel": "realestate_eg.contract_management.doctype.property_contract.property_contract.on_contract_cancel",
    },
    "Installment Payment": {
        "on_submit": "realestate_eg.installment_management.doctype.installment_payment.installment_payment.on_payment_submit",
        "on_cancel": "realestate_eg.installment_management.doctype.installment_payment.installment_payment.on_payment_cancel",
    },
    "Post Dated Cheque": {
        "on_update": "realestate_eg.pdc_management.doctype.post_dated_cheque.post_dated_cheque.on_pdc_update",
    },
    "Unit Cancellation": {
        "on_submit": "realestate_eg.cancellation_and_refund.doctype.unit_cancellation.unit_cancellation.on_cancellation_submit",
    },
    "Escrow Release Request": {
        "on_update": "realestate_eg.construction_management.doctype.escrow_release_request.escrow_release_request.on_release_update",
    },
    "Lease Contract": {
        "on_update": "realestate_eg.property_and_rental.doctype.lease_contract.lease_contract.on_lease_update",
    },
}

# --------------------------------------------------------------------------
# Scheduled Tasks
# --------------------------------------------------------------------------
scheduler_events = {
    "daily": [
        # Installment Management — mark overdue, calculate penalties, dunning
        "realestate_eg.utils.penalty_engine.check_overdue_installments",
        # PDC Management — flag cheques approaching maturity for bank submission
        "realestate_eg.utils.pdc_lifecycle.check_pdc_due_dates",
        # Lease Management — check for expiring leases
        "realestate_eg.utils.rental_law_engine.check_lease_expirations",
        # NUCA Compliance — check construction deadlines
        "realestate_eg.land_and_project_development.doctype.nuca_allocation.nuca_allocation.check_nuca_compliance",
    ],
    "weekly": [
        # Collection Forecast — generate forecast report data
        "realestate_eg.utils.installment_calculator.generate_collection_forecast",
        # Default Risk Scoring — rule-based scoring of installment plans
        "realestate_eg.utils.penalty_engine.run_default_risk_scoring",
    ],
    "monthly": [
        # Wadeea — calculate monthly investment yields on maintenance deposits
        "realestate_eg.facility_management.doctype.wadeea_deposit.wadeea_deposit.calculate_monthly_yields",
        # Rent Collection — auto-generate rent collection entries for active leases
        "realestate_eg.property_and_rental.doctype.rent_collection.rent_collection.generate_monthly_rent_entries",
        # Old Rent Transition — recalculate old rent amounts on anniversary
        "realestate_eg.utils.rental_law_engine.process_old_rent_transitions",
    ],
}

# --------------------------------------------------------------------------
# Fixtures — exported on bench export-fixtures
# --------------------------------------------------------------------------
fixtures = [
    {
        "dt": "Custom Field",
        "filters": [["module", "=", "Real Estate Egypt"]],
    },
    {
        "dt": "Property Setter",
        "filters": [["module", "=", "Real Estate Egypt"]],
    },
    {
        "dt": "Workflow",
        "filters": [["module", "=", "Real Estate Egypt"]],
    },
    {
        "dt": "Workflow State",
        "filters": [["module", "=", "Real Estate Egypt"]],
    },
    {
        "dt": "Workflow Action Master",
        "filters": [["module", "=", "Real Estate Egypt"]],
    },
    {
        "dt": "Print Format",
        "filters": [["module", "=", "Real Estate Egypt"]],
    },
    {
        "dt": "Notification",
        "filters": [["module", "=", "Real Estate Egypt"]],
    },
    {
        "dt": "Role",
        "filters": [
            [
                "name",
                "in",
                [
                    "Developer Admin",
                    "Sales Manager",
                    "Sales Agent",
                    "Finance Manager",
                    "Legal Counsel",
                    "Property Manager",
                    "Facility Manager",
                ],
            ]
        ],
    },
]

# --------------------------------------------------------------------------
# Website Generators
# --------------------------------------------------------------------------
website_generators = []

# --------------------------------------------------------------------------
# Jinja Environment
# --------------------------------------------------------------------------
jinja = {
    "methods": [
        "realestate_eg.utils.tax_utils.format_egp_currency",
        "realestate_eg.utils.tax_utils.get_eta_qr_code",
    ],
}

# --------------------------------------------------------------------------
# Installation
# --------------------------------------------------------------------------
after_install = "realestate_eg.setup.after_install"
after_migrate = "realestate_eg.setup.after_migrate"

# --------------------------------------------------------------------------
# User Data Protection
# --------------------------------------------------------------------------
user_data_fields = [
    {
        "doctype": "Buyer Profile",
        "filter_by": "customer",
        "redact_fields": ["national_id", "date_of_birth", "monthly_income"],
        "partial": 1,
    },
    {
        "doctype": "Tenant",
        "filter_by": "customer",
        "redact_fields": ["national_id", "phone", "email"],
        "partial": 1,
    },
]

# --------------------------------------------------------------------------
# Override Doctype Dashboards
# --------------------------------------------------------------------------
override_doctype_dashboards = {
    "Customer": "realestate_eg.overrides.customer.get_dashboard_data",
}
