frappe.ui.form.on("Utility Billing", {
    meter_reading_previous: function(frm) { frm.events._calc(frm); },
    meter_reading_current: function(frm) { frm.events._calc(frm); },
    rate_per_unit: function(frm) { frm.events._calc(frm); },
    
    _calc: function(frm) {
        if (frm.doc.meter_reading_current >= frm.doc.meter_reading_previous) {
            let cons = frm.doc.meter_reading_current - frm.doc.meter_reading_previous;
            frm.set_value("consumption", cons);
            frm.set_value("total_amount", cons * flt(frm.doc.rate_per_unit));
        }
    }
});
