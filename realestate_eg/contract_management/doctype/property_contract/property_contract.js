// Copyright (c) 2026, Nest Software Development and contributors
frappe.ui.form.on("Property Contract", {
    refresh: function (frm) {
        if (frm.doc.docstatus === 1 && frm.doc.status === "Active") {
            if (frm.doc.installment_plan) {
                frm.add_custom_button(__("View Installment Plan"), function () {
                    frappe.set_route("Form", "Installment Plan", frm.doc.installment_plan);
                });
            }
            frm.add_custom_button(__("Request Cancellation"), function () {
                frappe.new_doc("Unit Cancellation", {
                    property_contract: frm.doc.name,
                    property_unit: frm.doc.property_unit,
                    buyer_profile: frm.doc.buyer_profile,
                });
            }, __("Actions"));

            if (frm.doc.digital_signature_status === "Not Initiated") {
                frm.add_custom_button(__("Send for Signing"), function () {
                    frappe.call({
                        method: "realestate_eg.api.digital_signature.create_signing_request",
                        args: {
                            contract_name: frm.doc.name,
                            signer_name: frm.doc.buyer_profile,
                            signer_email: "",
                        },
                        callback: function (r) {
                            if (r.message && r.message.status === "success") {
                                frappe.msgprint(__("Signing request sent!"));
                                frm.reload_doc();
                            }
                        },
                    });
                }, __("Actions"));
            }
        }
    },
    total_unit_price: function (frm) { _calc(frm); },
    down_payment_pct: function (frm) { _calc(frm); },
    reservation_fee: function (frm) { _calc(frm); },
    property_unit: function (frm) {
        if (frm.doc.property_unit) {
            frappe.db.get_value("Property Unit", frm.doc.property_unit, "total_price", (r) => {
                if (r) frm.set_value("total_unit_price", r.total_price);
            });
        }
    },
});

function _calc(frm) {
    let dp = flt(frm.doc.total_unit_price) * flt(frm.doc.down_payment_pct) / 100;
    frm.set_value("down_payment_amount", flt(dp, 2));
    frm.set_value("financed_amount", flt(frm.doc.total_unit_price - flt(frm.doc.reservation_fee) - dp, 2));
}
