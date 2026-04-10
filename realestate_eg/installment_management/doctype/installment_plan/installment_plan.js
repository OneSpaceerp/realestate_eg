// Copyright (c) 2026, Nest Software Development and contributors
// For license information, please see license.txt

frappe.ui.form.on("Installment Plan", {
    refresh: function (frm) {
        // Dashboard summary
        if (frm.doc.status === "Active") {
            frm.dashboard.add_indicator(__("Active"), "blue");
            frm.dashboard.add_indicator(
                __("Paid: {0}%", [frm.doc.completion_pct || 0]),
                frm.doc.completion_pct > 75 ? "green" : "orange"
            );
            if (frm.doc.overdue_amount > 0) {
                frm.dashboard.add_indicator(
                    __("Overdue: {0}", [format_currency(frm.doc.overdue_amount)]),
                    "red"
                );
            }
        } else if (frm.doc.status === "Fully Paid") {
            frm.dashboard.add_indicator(__("Fully Paid"), "green");
        }

        // Custom buttons
        if (frm.doc.docstatus === 1 && frm.doc.status === "Active") {
            frm.add_custom_button(__("Record Payment"), function () {
                frappe.new_doc("Installment Payment", {
                    installment_plan: frm.doc.name,
                    buyer_profile: frm.doc.buyer_profile,
                    property_unit: frm.doc.property_unit,
                    company: frm.doc.company,
                });
            }, __("Actions"));

            frm.add_custom_button(__("Early Settlement"), function () {
                frappe.new_doc("Early Settlement", {
                    installment_plan: frm.doc.name,
                });
            }, __("Actions"));

            frm.add_custom_button(__("Restructure"), function () {
                frappe.new_doc("Plan Restructuring", {
                    installment_plan: frm.doc.name,
                });
            }, __("Actions"));

            frm.add_custom_button(__("Regenerate Schedule"), function () {
                frappe.confirm(
                    __("This will regenerate the installment schedule. Continue?"),
                    function () {
                        frm.call("regenerate_schedule").then(() => frm.reload_doc());
                    }
                );
            }, __("Admin"));
        } else if (!frm.doc.docstatus) {
            frm.add_custom_button(__("Generate Schedule"), function () {
                if (!frm.doc.total_unit_price || !frm.doc.plan_start_date || !frm.doc.plan_duration_months) {
                    frappe.msgprint(__("Please fill Total Unit Price, Start Date, and Duration first."));
                    return;
                }
                frm.call({
                    method: "get_preview_schedule",
                    doc: frm.doc,
                    callback: function(r) {
                        if (r.message && r.message.length > 0) {
                            frm.clear_table("schedule");
                            r.message.forEach(row => {
                                let c = frm.add_child("schedule");
                                c.due_date = row.due_date;
                                c.amount = row.amount;
                                c.penalty_amount = row.penalty_amount;
                                c.total_due = row.total_due;
                                c.paid_amount = row.paid_amount;
                                c.balance = row.balance;
                                c.status = row.status;
                                c.days_overdue = row.days_overdue;
                                c.idx = row.idx;
                            });
                            frm.refresh_field("schedule");
                        }
                    }
                });
            }, __("Actions"));
        }
    },

    validate: function(frm) {
        // Clear empty default rows so server-side can auto-generate
        if (frm.doc.schedule && frm.doc.schedule.length > 0) {
            let has_content = false;
            frm.doc.schedule.forEach(row => {
                if (row.amount) has_content = true;
            });
            if (!has_content) {
                frm.clear_table("schedule");
            }
        }
    },

    total_unit_price: function (frm) {
        calc_financials(frm);
    },

    down_payment_pct: function (frm) {
        calc_financials(frm);
    },

    reservation_fee: function (frm) {
        calc_financials(frm);
    },
});

function calc_financials(frm) {
    let dp_amount = flt(frm.doc.total_unit_price) * flt(frm.doc.down_payment_pct) / 100;
    frm.set_value("down_payment_amount", flt(dp_amount, 2));
    let financed = flt(frm.doc.total_unit_price) - flt(frm.doc.reservation_fee) - dp_amount;
    frm.set_value("financed_amount", flt(financed, 2));
}
