frappe.ui.form.on("Project Cost Line", {
    estimated_cost: function(frm, cdt, cdn) { frm.events._calc(frm); },
    actual_cost: function(frm, cdt, cdn) { frm.events._calc(frm); },
    cost_lines_remove: function(frm) { frm.events._calc(frm); }
});

frappe.ui.form.on("Cost Budget", {
    _calc: function(frm) {
        let est = 0; let act = 0;
        (frm.doc.cost_lines || []).forEach(d => {
            frappe.model.set_value(d.doctype, d.name, "variance", flt(d.estimated_cost) - flt(d.actual_cost));
            est += flt(d.estimated_cost);
            act += flt(d.actual_cost);
        });
        frm.set_value("total_estimated_cost", est);
        frm.set_value("total_actual_cost", act);
    }
});
