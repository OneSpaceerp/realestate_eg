frappe.ui.form.on("Lease Contract", {
    lease_start_date: function(frm) { frm.events._calc(frm); },
    lease_end_date: function(frm) { frm.events._calc(frm); },
    monthly_rent: function(frm) { frm.events._calc(frm); },
    annual_increase_pct: function(frm) { frm.events._calc(frm); },
    
    _calc: function(frm) {
        if (frm.doc.lease_start_date && frm.doc.lease_end_date && frm.doc.monthly_rent) {
            frm.clear_table("rent_schedule");
            frm.save();
        }
    }
});
