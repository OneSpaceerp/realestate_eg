frappe.ui.form.on("Refund Schedule", {
    number_of_payments: function(frm) {
        if (frm.doc.total_refund_amount > 0 && frm.doc.number_of_payments > 0) {
            frm.clear_table("refund_payments");
            frm.save();
        }
    }
});
