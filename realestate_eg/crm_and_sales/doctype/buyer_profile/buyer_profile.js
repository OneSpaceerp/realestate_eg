frappe.ui.form.on("Buyer Profile", {
    refresh: function(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__("View Contracts"), function() {
                frappe.set_route("List", "Property Contract", { buyer_profile: frm.doc.name });
            });
            frm.add_custom_button(__("View Installments"), function() {
                frappe.set_route("List", "Installment Plan", { buyer_profile: frm.doc.name });
            });
        }
    }
});
