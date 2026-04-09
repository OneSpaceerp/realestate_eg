frappe.ui.form.on("Property Quotation", {
    property_price: function(frm) { frm.events._calc(frm); },
    discount_pct: function(frm) { frm.events._calc(frm); },
    payment_plan_months: function(frm) { frm.events._calc(frm); },
    down_payment_pct: function(frm) { frm.events._calc(frm); },
    
    _calc: function(frm) {
        let price = flt(frm.doc.property_price);
        let dis = price * flt(frm.doc.discount_pct) / 100;
        let net = price - dis;
        frm.set_value("discount_amount", flt(dis, 2));
        frm.set_value("net_price", flt(net, 2));
        
        let dp = net * flt(frm.doc.down_payment_pct) / 100;
        frm.set_value("down_payment_amount", flt(dp, 2));
        
        if (frm.doc.payment_plan_months > 0) {
            frm.set_value("installment_amount", flt((net - dp) / frm.doc.payment_plan_months, 2));
        }
    }
});
