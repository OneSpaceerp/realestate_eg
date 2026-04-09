// Copyright (c) 2026, Nest Software Development and contributors
frappe.ui.form.on("Installment Payment", {
    refresh: function (frm) {
        frm.set_query("installment_plan", function () {
            return { filters: { status: "Active", docstatus: 1 } };
        });
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
                    }
                },
            });
        }
    },
});
