frappe.ui.form.on("Plan Restructuring", {
    installment_plan: function(frm) { frm.events._calc(frm); },
    restructure_fee_pct: function(frm) { frm.events._calc(frm); },
    restructure_fee_amount: function(frm) { frm.events._calc(frm); },
    new_duration_months: function(frm) { frm.events._calc(frm); },
    new_frequency: function(frm) { frm.events._calc(frm); },
    
    _calc: function(frm) {
        if (!frm.doc.original_outstanding) return;
        let base = flt(frm.doc.original_outstanding);
        let pct_fee = base * flt(frm.doc.restructure_fee_pct) / 100;
        let new_fin = base + pct_fee + flt(frm.doc.restructure_fee_amount);
        frm.set_value("new_financed_amount", new_fin);

        if (frm.doc.new_duration_months) {
            const freq_map = { "Monthly": 1, "Quarterly": 3, "Semi-Annual": 6, "Annual": 12 };
            let divisor = frm.doc.new_duration_months / (freq_map[frm.doc.new_frequency] || 1);
            if (divisor > 0) {
                frm.set_value("new_installment_amount", new_fin / divisor);
            }
        }
    }
});
