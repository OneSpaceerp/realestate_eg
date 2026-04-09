frappe.ui.form.on("Early Settlement", {
    original_outstanding: function(frm) { frm.events._calc(frm); },
    discount_pct: function(frm) { frm.events._calc(frm); },
    
    _calc: function(frm) {
        if (!frm.doc.original_outstanding) return;
        let base = flt(frm.doc.original_outstanding);
        let dis = base * flt(frm.doc.discount_pct) / 100;
        frm.set_value("discount_amount", flt(dis, 2));
        frm.set_value("net_settlement_amount", flt(base - dis, 2));
    }
});
