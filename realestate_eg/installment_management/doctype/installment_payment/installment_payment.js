// Copyright (c) 2026, Nest Software Development and contributors
frappe.ui.form.on("Installment Payment", {
    refresh: function (frm) {
        frm.set_query("installment_plan", function () {
            return { filters: { status: "Active", docstatus: 1 } };
        });
        
        if (frm.doc.docstatus === 1) {
            if (frm.doc.payment_entry) {
                frm.add_custom_button(__("Payment Ledger"), function() {
                    frappe.set_route("query-report", "General Ledger", {
                        voucher_no: frm.doc.payment_entry
                    });
                }, __("View"));
            }
            if (frm.doc.recognition_journal) {
                frm.add_custom_button(__("Recognition Ledger"), function() {
                    frappe.set_route("query-report", "General Ledger", {
                        voucher_no: frm.doc.recognition_journal
                    });
                }, __("View"));
            }
        }
    },
    installment_plan: function (frm) {
        if (frm.doc.installment_plan) {
            frappe.call({
                method: "frappe.client.get",
                args: { doctype: "Installment Plan", name: frm.doc.installment_plan },
                callback: function (r) {
                    if (r.message) {
                        frm.set_value("buyer_profile", r.message.buyer_profile);
                        frm.set_value("property_unit", r.message.property_unit);
                        frm.set_value("company", r.message.company);
                        
                        // Auto-fetch the next unpaid schedule row
                        if (r.message.schedule && r.message.schedule.length > 0) {
                            let next_row = r.message.schedule.find(row => 
                                ["Upcoming", "Due", "Overdue", "Partially Paid"].includes(row.status) && row.balance > 0
                            );
                            
                            if (next_row) {
                                frm.set_value("schedule_row_idx", next_row.idx);
                                frm.set_value("amount", next_row.balance);
                            }
                        }
                    }
                },
            });
        }
    },
});
