// Copyright (c) 2026, Nest Software Development and contributors
// For license information, please see license.txt

frappe.ui.form.on("Property Unit", {
    refresh: function (frm) {
        // Status indicators
        const status_colors = {
            "Available": "green",
            "Reserved": "blue",
            "Under Contract": "orange",
            "Sold": "purple",
            "Delivered": "darkgrey",
            "Cancelled": "red",
            "Resale": "yellow",
        };
        if (frm.doc.status) {
            frm.dashboard.add_indicator(
                __(frm.doc.status),
                status_colors[frm.doc.status] || "grey"
            );
        }

        // Filter linked fields by hierarchy
        frm.set_query("phase", function () {
            return { filters: { project: frm.doc.project } };
        });
        frm.set_query("zone", function () {
            return { filters: { phase: frm.doc.phase } };
        });
        frm.set_query("building", function () {
            return { filters: { zone: frm.doc.zone } };
        });

        // Action buttons
        if (frm.doc.status === "Available" && !frm.is_new()) {
            frm.add_custom_button(__("Create Quotation"), function () {
                frappe.new_doc("Property Quotation", {
                    property_unit: frm.doc.name,
                });
            }, __("Actions"));

            frm.add_custom_button(__("Reserve"), function () {
                frm.set_value("status", "Reserved");
                frm.save();
            }, __("Actions"));
        }

        if (frm.doc.status === "Sold" || frm.doc.status === "Under Contract") {
            frm.add_custom_button(__("View Installment Plan"), function () {
                if (frm.doc.installment_plan) {
                    frappe.set_route("Form", "Installment Plan", frm.doc.installment_plan);
                } else {
                    frappe.msgprint(__("No installment plan linked."));
                }
            }, __("View"));
        }
    },

    validate: function (frm) {
        // Auto-calculate total price
        _calculate_price(frm);
    },

    base_price_per_sqm: function (frm) {
        _calculate_price(frm);
    },

    built_up_area_sqm: function (frm) {
        _calculate_price(frm);
    },

    garden_area_sqm: function (frm) {
        _calculate_price(frm);
    },

    roof_area_sqm: function (frm) {
        _calculate_price(frm);
    },
});

function _calculate_price(frm) {
    let base = flt(frm.doc.base_price_per_sqm) * flt(frm.doc.built_up_area_sqm);
    let garden = flt(frm.doc.garden_area_sqm) * flt(frm.doc.base_price_per_sqm) * 0.5;
    let roof = flt(frm.doc.roof_area_sqm) * flt(frm.doc.base_price_per_sqm) * 0.3;
    frm.set_value("total_price", flt(base + garden + roof, 2));
}
