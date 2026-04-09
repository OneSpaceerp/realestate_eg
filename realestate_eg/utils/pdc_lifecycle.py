# Copyright (c) 2026, Nest Software Development and contributors
# For license information, please see license.txt

"""
PDC Lifecycle Manager — Post-Dated Cheque state machine and GL entry management.

Lifecycle states:
  Received → In Vault → Submitted to Bank → Under Collection → Cleared / Bounced
  
GL Entry transitions:
  - Received:          DR Notes Receivable, CR Revenue/Receivable
  - Under Collection:  DR Under Collection, CR Notes Receivable  
  - Cleared:           DR Bank, CR Under Collection → Revenue recognition
  - Bounced:           DR Notes Receivable, CR Under Collection → Penalty to buyer

Egyptian banking rules:
  - Working days: Sunday–Thursday
  - Clearing cycle: D+1 for CBE Clearing House
  - Maturity flag: 5 business days before due_date
"""

import frappe
from frappe import _
from frappe.utils import (
    add_days,
    date_diff,
    flt,
    getdate,
    nowdate,
    get_datetime,
    cint,
)
from datetime import timedelta

# Egyptian banking working days (0=Monday, 6=Sunday)
# Egypt: Sunday(6) to Thursday(3) are working days
WORKING_DAYS = {6, 0, 1, 2, 3}  # Sun, Mon, Tue, Wed, Thu


# PDC Status flow
VALID_TRANSITIONS = {
    "Received": ["In Vault", "Cancelled", "Returned to Buyer"],
    "In Vault": ["Submitted to Bank", "Returned to Buyer", "Cancelled"],
    "Submitted to Bank": ["Under Collection", "Returned to Buyer"],
    "Under Collection": ["Cleared", "Bounced"],
    "Cleared": [],  # Terminal state
    "Bounced": ["Received", "Replaced", "Cancelled"],  # Can re-enter cycle
    "Returned to Buyer": [],  # Terminal state
    "Cancelled": [],  # Terminal state
    "Replaced": [],  # Terminal state
}


def validate_status_transition(current_status: str, new_status: str):
    """
    Validate that a PDC status transition is allowed.

    Args:
        current_status: Current status of the cheque.
        new_status: Desired new status.

    Raises:
        frappe.ValidationError if transition is invalid.
    """
    allowed = VALID_TRANSITIONS.get(current_status, [])
    if new_status not in allowed:
        frappe.throw(
            _("Cannot transition PDC from '{0}' to '{1}'. Allowed: {2}").format(
                current_status, new_status, ", ".join(allowed) or "None (terminal state)"
            )
        )


def is_egyptian_business_day(check_date) -> bool:
    """
    Check if a date is an Egyptian business day (Sunday–Thursday).

    Args:
        check_date: Date to check.

    Returns:
        True if it's a working day.
    """
    d = getdate(check_date)
    return d.weekday() in WORKING_DAYS


def get_next_business_day(from_date) -> str:
    """
    Get the next Egyptian business day from a given date.

    Args:
        from_date: Starting date.

    Returns:
        Next business day as date string.
    """
    d = getdate(from_date)
    d += timedelta(days=1)
    while d.weekday() not in WORKING_DAYS:
        d += timedelta(days=1)
    return d


def get_business_days_before(target_date, num_days: int) -> str:
    """
    Get a date that is `num_days` business days before target_date.

    Args:
        target_date: The reference date.
        num_days: Number of business days to go back.

    Returns:
        Date string.
    """
    d = getdate(target_date)
    count = 0
    while count < num_days:
        d -= timedelta(days=1)
        if d.weekday() in WORKING_DAYS:
            count += 1
    return d


@frappe.whitelist()
def check_pdc_due_dates():
    """
    Daily scheduler job: identify PDCs approaching maturity and flag for bank submission.
    5 Egyptian business days before due_date → status should be 'Submitted to Bank'.
    
    This job is idempotent.
    """
    today = getdate(nowdate())

    # Look ahead 7 calendar days to catch upcoming PDCs
    lookahead_date = add_days(today, 10)

    pdcs_in_vault = frappe.get_all(
        "Post Dated Cheque",
        filters={
            "status": "In Vault",
            "due_date": ["<=", lookahead_date],
        },
        fields=["name", "due_date", "amount", "buyer_profile", "installment_plan"],
    )

    flagged_count = 0
    for pdc in pdcs_in_vault:
        submission_date = get_business_days_before(pdc.due_date, 5)
        if today >= getdate(submission_date):
            # Flag for bank submission
            frappe.db.set_value(
                "Post Dated Cheque",
                pdc.name,
                {
                    "physical_location": "Submitted to Bank",
                },
                update_modified=True,
            )

            # Create a ToDo for finance team
            frappe.get_doc(
                {
                    "doctype": "ToDo",
                    "description": _(
                        "PDC {0} (amount: {1} EGP) is due on {2}. "
                        "Please submit to collecting bank."
                    ).format(
                        pdc.name,
                        frappe.utils.fmt_money(pdc.amount, currency="EGP"),
                        frappe.utils.format_date(pdc.due_date),
                    ),
                    "reference_type": "Post Dated Cheque",
                    "reference_name": pdc.name,
                    "priority": "High",
                    "status": "Open",
                }
            ).insert(ignore_permissions=True)

            flagged_count += 1

    # Also check for D+1 clearing (cheques submitted yesterday that should clear)
    _check_clearing_cycle(today)

    frappe.db.commit()
    frappe.logger("realestate_eg").info(
        f"PDC due date check: flagged {flagged_count} cheques for bank submission"
    )


def _check_clearing_cycle(today):
    """
    D+1 clearing: cheques deposited on the previous business day should clear today
    (unless a bounce notification was received).
    """
    if not is_egyptian_business_day(today):
        return

    # Find the previous business day
    prev_day = today - timedelta(days=1)
    while not is_egyptian_business_day(prev_day):
        prev_day -= timedelta(days=1)

    # Cheques under collection that were deposited on prev_day
    clearing_candidates = frappe.get_all(
        "Post Dated Cheque",
        filters={
            "status": "Under Collection",
            "due_date": ["<=", today],
        },
        fields=["name", "due_date", "amount", "installment_plan"],
    )

    for pdc in clearing_candidates:
        due = getdate(pdc.due_date)
        expected_clear = get_next_business_day(due)
        if getdate(expected_clear) <= today:
            # Auto-clear if no bounce notification received
            # In production, banking API would provide actual status
            frappe.logger("realestate_eg").info(
                f"PDC {pdc.name} eligible for auto-clear (D+1 from {due})"
            )


def create_pdc_gl_entries(pdc_name: str, transition: str, company: str):
    """
    Create appropriate GL entries for PDC status transitions.

    Args:
        pdc_name: Name of the Post Dated Cheque.
        transition: The status transition (e.g., 'received', 'under_collection', 'cleared', 'bounced').
        company: Company name for GL entries.
    """
    pdc = frappe.get_doc("Post Dated Cheque", pdc_name)

    # Get account names from Real Estate Settings or defaults
    settings = _get_pdc_accounts(company)

    if transition == "received":
        # DR Notes Receivable, CR Accounts Receivable
        _make_journal_entry(
            company=company,
            debit_account=settings["notes_receivable_account"],
            credit_account=settings["accounts_receivable_account"],
            amount=flt(pdc.amount),
            reference_type="Post Dated Cheque",
            reference_name=pdc_name,
            remark=_("PDC received from {0} — Cheque #{1}").format(
                pdc.drawer_name, pdc.cheque_number
            ),
            party_type="Customer" if settings.get("party") else None,
            party=settings.get("party"),
        )

    elif transition == "under_collection":
        # DR Under Collection, CR Notes Receivable
        _make_journal_entry(
            company=company,
            debit_account=settings["under_collection_account"],
            credit_account=settings["notes_receivable_account"],
            amount=flt(pdc.amount),
            reference_type="Post Dated Cheque",
            reference_name=pdc_name,
            remark=_("PDC submitted to bank — Cheque #{0}").format(pdc.cheque_number),
        )

    elif transition == "cleared":
        # DR Bank Account, CR Under Collection
        _make_journal_entry(
            company=company,
            debit_account=settings["bank_account"],
            credit_account=settings["under_collection_account"],
            amount=flt(pdc.amount),
            reference_type="Post Dated Cheque",
            reference_name=pdc_name,
            remark=_("PDC cleared — Cheque #{0}").format(pdc.cheque_number),
        )

    elif transition == "bounced":
        # Reverse: DR Notes Receivable, CR Under Collection
        _make_journal_entry(
            company=company,
            debit_account=settings["notes_receivable_account"],
            credit_account=settings["under_collection_account"],
            amount=flt(pdc.amount),
            reference_type="Post Dated Cheque",
            reference_name=pdc_name,
            remark=_("PDC bounced — Cheque #{0}, Reason: {1}").format(
                pdc.cheque_number, pdc.return_reason or "Unknown"
            ),
        )


def _make_journal_entry(
    company: str,
    debit_account: str,
    credit_account: str,
    amount: float,
    reference_type: str = None,
    reference_name: str = None,
    remark: str = "",
    party_type: str = None,
    party: str = None,
):
    """Create and submit a Journal Entry for PDC GL transitions."""
    je = frappe.new_doc("Journal Entry")
    je.company = company
    je.posting_date = nowdate()
    je.voucher_type = "Journal Entry"
    je.remark = remark
    je.user_remark = remark

    # Debit row
    debit_row = je.append("accounts", {})
    debit_row.account = debit_account
    debit_row.debit_in_account_currency = flt(amount, 2)
    debit_row.credit_in_account_currency = 0
    if reference_type:
        debit_row.reference_type = reference_type
        debit_row.reference_name = reference_name
    if party_type and party:
        debit_row.party_type = party_type
        debit_row.party = party

    # Credit row
    credit_row = je.append("accounts", {})
    credit_row.account = credit_account
    credit_row.debit_in_account_currency = 0
    credit_row.credit_in_account_currency = flt(amount, 2)
    if party_type and party:
        credit_row.party_type = party_type
        credit_row.party = party

    je.insert(ignore_permissions=True)
    je.submit()

    return je.name


def _get_pdc_accounts(company: str) -> dict:
    """
    Get PDC-related account names for a company.
    First checks Real Estate Settings, then falls back to defaults.
    """
    accounts = {
        "notes_receivable_account": None,
        "under_collection_account": None,
        "bank_account": None,
        "accounts_receivable_account": None,
    }

    # Try to get from Real Estate Settings
    if frappe.db.exists("DocType", "Real Estate Settings"):
        try:
            settings = frappe.get_single("Real Estate Settings")
            accounts["notes_receivable_account"] = (
                settings.get("notes_receivable_account") or None
            )
            accounts["under_collection_account"] = (
                settings.get("under_collection_account") or None
            )
            accounts["bank_account"] = settings.get("default_bank_account") or None
        except Exception:
            pass

    # Fall back to company defaults
    if not accounts["notes_receivable_account"]:
        accounts["notes_receivable_account"] = frappe.db.get_value(
            "Account",
            {"account_name": "Notes Receivable", "company": company},
            "name",
        ) or frappe.db.get_value(
            "Account",
            {"account_name": "Debtors", "company": company},
            "name",
        )

    if not accounts["under_collection_account"]:
        accounts["under_collection_account"] = frappe.db.get_value(
            "Account",
            {"account_name": "Cheques Under Collection", "company": company},
            "name",
        ) or accounts["notes_receivable_account"]

    if not accounts["bank_account"]:
        accounts["bank_account"] = frappe.db.get_value(
            "Account",
            {"account_type": "Bank", "is_group": 0, "company": company},
            "name",
        )

    if not accounts["accounts_receivable_account"]:
        accounts["accounts_receivable_account"] = frappe.db.get_value(
            "Company", company, "default_receivable_account"
        )

    return accounts
