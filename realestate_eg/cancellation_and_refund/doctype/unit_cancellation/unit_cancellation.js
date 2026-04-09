// Copyright (c) 2026, Nest Software Development and contributors
frappe.ui.form.on("Unit Cancellation", {
    refresh: function(frm) {
        if (frm.doc.docstatus === 1 && frm.doc.status === "Submitted") {
            frm.add_custom_button(__("Approve"), function() {
                frm.set_value("status", "Approved");
                frm.save();
            }, __("Actions"));
            frm.add_custom_button(__("Reject"), function() {
                frm.set_value("status", "Rejected");
                frm.save();
            }, __("Actions"));
        }
    },
    total_amount_paid: function(frm) { _calc_deduction(frm); },
    project_completion_pct: function(frm) { _calc_deduction(frm); },
    is_developer_delay: function(frm) { _calc_deduction(frm); },
});

function _calc_deduction(frm) {
    if (frm.doc.is_developer_delay) {
        frm.set_value("deduction_pct", 0);
        frm.set_value("deduction_amount", 0);
        frm.set_value("net_refund_amount", flt(frm.doc.total_amount_paid));
        return;
    }
    let pct = flt(frm.doc.project_completion_pct);
    let deduction = pct < 60 ? 10 : pct < 80 ? 25 : 40;
    let deduction_amt = flt(frm.doc.total_amount_paid) * deduction / 100;
    frm.set_value("deduction_pct", deduction);
    frm.set_value("deduction_amount", flt(deduction_amt, 2));
    frm.set_value("net_refund_amount", flt(frm.doc.total_amount_paid - deduction_amt, 2));
}
