# Copyright (c) 2026, Nest Software Development and contributors
import frappe
from frappe import _
from frappe.utils import flt
from frappe.model.document import Document
from realestate_eg.utils.pdc_lifecycle import create_pdc_gl_entries

class ChequeBatchDeposit(Document):
    def validate(self):
        self._calculate_totals()
        self._validate_cheques()

    def on_submit(self):
        self._update_pdc_status("Submitted to Bank")
        self.status = "Submitted to Bank"
        self.db_set("status", "Submitted to Bank", update_modified=False)

    def on_cancel(self):
        self._update_pdc_status("In Vault")
        self.status = "Cancelled"
        self.db_set("status", "Cancelled", update_modified=False)

    def _calculate_totals(self):
        self.total_cheques = len(self.cheques)
        self.total_amount = sum(flt(row.amount) for row in self.cheques)

    def _validate_cheques(self):
        cheque_list = []
        for row in self.cheques:
            if row.post_dated_cheque in cheque_list:
                frappe.throw(_("Cheque {0} appears twice in the batch.").format(row.post_dated_cheque))
            cheque_list.append(row.post_dated_cheque)
            
            status = frappe.db.get_value("Post Dated Cheque", row.post_dated_cheque, "status")
            if status != "In Vault":
                frappe.throw(_("Cheque {0} must be 'In Vault' to be deposited. Current status: {1}").format(
                    row.post_dated_cheque, status
                ))

    def _update_pdc_status(self, split_status):
        for row in self.cheques:
            pdc = frappe.get_doc("Post Dated Cheque", row.post_dated_cheque)
            pdc.status = split_status
            pdc.save(ignore_permissions=True)

    @frappe.whitelist()
    def generate_ach_file(self):
        """Generate ISO 20022 pain.001 ACH file via Banking Integration."""
        if not self.cheques:
            return
        try:
            from realestate_eg.api.banking_integration import generate_pain001_file
            # In a real impl, this returns a file URL or content
            file_data = generate_pain001_file(batch_name=self.name, cheques=self.cheques)
            self.iso20022_generated = 1
            if file_data and "file_url" in file_data:
                 self.clearing_file_url = file_data["file_url"]
            self.save()
            frappe.msgprint(_("ACH Clearning File generated successfully."), indicator="green")
        except Exception as e:
            frappe.throw(_("Failed to generate ACH clearing file: {0}").format(str(e)))
