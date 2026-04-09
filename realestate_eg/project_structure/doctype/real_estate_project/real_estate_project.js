// Copyright (c) 2026, Nest Software Development and contributors
frappe.ui.form.on("Real Estate Project", {
    refresh: function (frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__("View Units"), function () {
                frappe.set_route("List", "Property Unit", { project: frm.doc.name });
            });
            frm.add_custom_button(__("Create Phase"), function () {
                frappe.new_doc("Project Phase", { project: frm.doc.name });
            }, __("Create"));
        }
    },
});
