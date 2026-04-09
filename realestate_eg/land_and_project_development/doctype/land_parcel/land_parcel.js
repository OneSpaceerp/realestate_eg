// Copyright (c) 2026, Nest Software Development and contributors
// For license information, please see license.txt

frappe.ui.form.on("Land Parcel", {
    refresh: function (frm) {
        // Dashboard indicators
        if (frm.doc.status === "Acquired") {
            frm.dashboard.add_indicator(
                __("Acquired"),
                "green"
            );
        } else if (frm.doc.status === "Under Negotiation") {
            frm.dashboard.add_indicator(
                __("Under Negotiation"),
                "orange"
            );
        }

        // Custom buttons
        if (frm.doc.status === "Acquired" && !frm.doc.linked_project) {
            frm.add_custom_button(
                __("Create Project"),
                function () {
                    frappe.new_doc("Real Estate Project", {
                        land_parcel: frm.doc.name,
                        location: frm.doc.location,
                        governorate: frm.doc.governorate,
                    });
                },
                __("Actions")
            );
        }

        if (
            frm.doc.acquisition_type === "NUCA Allocation" &&
            !frm.doc.nuca_allocation
        ) {
            frm.add_custom_button(
                __("Create NUCA Allocation"),
                function () {
                    frappe.new_doc("NUCA Allocation", {
                        land_parcel: frm.doc.name,
                    });
                },
                __("Actions")
            );
        }
    },

    validate: function (frm) {
        // Auto-calculate transfer tax
        if (frm.doc.total_cost) {
            frm.set_value(
                "transfer_tax_amount",
                flt(frm.doc.total_cost * 0.025, 2)
            );
        }
    },

    total_cost: function (frm) {
        frm.set_value(
            "transfer_tax_amount",
            flt(frm.doc.total_cost * 0.025, 2)
        );
    },

    acquisition_type: function (frm) {
        // Show/hide NUCA allocation field
        frm.toggle_reqd(
            "nuca_allocation",
            frm.doc.acquisition_type === "NUCA Allocation"
        );
    },
});
