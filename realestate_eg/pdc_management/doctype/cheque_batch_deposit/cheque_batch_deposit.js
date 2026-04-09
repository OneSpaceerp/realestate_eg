// Copyright (c) 2026, Nest Software Development and contributors
frappe.ui.form.on("Cheque Batch Deposit", {
    refresh: function(frm) {
        if (frm.doc.docstatus === 1 && !frm.doc.iso20022_generated && frm.doc.status === "Submitted to Bank") {
            frm.add_custom_button(__("Generate ACH File"), function() {
                frm.call("generate_ach_file").then(() => frm.reload_doc());
            }, __("Banking"));
        }
    }
});

frappe.ui.form.on("Cheque Batch Item", {
    post_dated_cheque: function(frm, cdt, cdn) {
        frm.events._calc(frm);
    },
    cheques_remove: function(frm) {
        frm.events._calc(frm);
    }
});

frappe.ui.form.on("Cheque Batch Deposit", {
    _calc: function(frm) {
        let total = 0;
        let count = 0;
        (frm.doc.cheques || []).forEach(row => {
            total += flt(row.amount);
            count++;
        });
        frm.set_value("total_amount", total);
        frm.set_value("total_cheques", count);
    }
});
