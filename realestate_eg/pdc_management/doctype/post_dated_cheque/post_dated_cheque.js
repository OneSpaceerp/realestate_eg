// Copyright (c) 2026, Nest Software Development and contributors
frappe.ui.form.on("Post Dated Cheque", {
    refresh: function (frm) {
        const status_colors = {
            "Received": "blue", "In Vault": "purple", "Submitted to Bank": "orange",
            "Under Collection": "yellow", "Cleared": "green", "Bounced": "red",
            "Returned to Buyer": "grey", "Cancelled": "darkgrey", "Replaced": "grey",
        };
        if (frm.doc.status) {
            frm.dashboard.add_indicator(__(frm.doc.status), status_colors[frm.doc.status] || "grey");
        }

        // Status transition buttons
        if (frm.doc.status === "Received") {
            frm.add_custom_button(__("Move to Vault"), function () {
                frm.set_value("status", "In Vault");
                frm.save();
            }, __("Actions"));
        }
        if (frm.doc.status === "In Vault") {
            frm.add_custom_button(__("Submit to Bank"), function () {
                frm.set_value("status", "Submitted to Bank");
                frm.save();
            }, __("Actions"));
        }
        if (frm.doc.status === "Submitted to Bank") {
            frm.add_custom_button(__("Mark Under Collection"), function () {
                frm.set_value("status", "Under Collection");
                frm.save();
            }, __("Actions"));
        }
        if (frm.doc.status === "Under Collection") {
            frm.add_custom_button(__("Mark Cleared"), function () {
                frm.set_value("status", "Cleared");
                frm.save();
            }, __("Clear"));
            frm.add_custom_button(__("Mark Bounced"), function () {
                frm.set_value("status", "Bounced");
                frm.save();
            }, __("Clear"));
        }

        // OCR button
        if (frm.doc.cheque_image && !frm.doc.ocr_verified) {
            frm.add_custom_button(__("Scan with OCR"), function () {
                frm.call("scan_with_ocr").then(() => frm.reload_doc());
            });
        }
    },
});
