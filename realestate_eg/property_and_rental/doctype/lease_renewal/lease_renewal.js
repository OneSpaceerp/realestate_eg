frappe.ui.form.on("Lease Renewal", {
    old_rent: function(frm) { frm.events._calc(frm); },
    increase_pct: function(frm) { frm.events._calc(frm); },
    
    _calc: function(frm) {
        if (frm.doc.old_rent) {
            frm.set_value("new_rent", flt(frm.doc.old_rent) * (1 + flt(frm.doc.increase_pct)/100));
        }
    }
});
