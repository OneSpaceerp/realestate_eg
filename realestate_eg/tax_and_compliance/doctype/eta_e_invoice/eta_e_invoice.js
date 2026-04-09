// Copyright (c) 2026, Nest Software Development and contributors
frappe.ui.form.on("ETA E-Invoice", {
    refresh: function(frm) {
        if (frm.doc.submission_status === "Pending") {
            frm.add_custom_button(__("Submit to ETA"), function() {
                frappe.call({
                    method: "realestate_eg.api.eta_integration.submit_invoice",
                    args: { eta_invoice_name: frm.doc.name },
                    callback: function() { frm.reload_doc(); },
                });
            });
        }
        if (frm.doc.eta_qr_code) {
            frm.add_custom_button(__("View QR"), function() {
                window.open(frm.doc.eta_qr_code, "_blank");
            });
        }
    },
});
