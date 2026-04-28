// Copyright (c) 2026, Nest Software Development and contributors
frappe.ui.form.on("Real Estate Project", {
    refresh: function (frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__("View Units"), function () {
                frappe.set_route("List", "Property Unit", { project: frm.doc.name });
            });
            frm.add_custom_button(__("Create Phase"), function () {
                frappe.new_doc("Project Phase", { project: frm.doc.name });
            }, __("Create"));

            frm.add_custom_button(__("Allocate Costs"), function () {
                let d = new frappe.ui.Dialog({
                    title: 'Allocate Project Costs',
                    fields: [
                        {
                            label: 'Cost Type',
                            fieldname: 'cost_type',
                            fieldtype: 'Select',
                            options: 'Land\nInfrastructure',
                            reqd: 1
                        },
                        {
                            label: 'Total Amount',
                            fieldname: 'total_cost',
                            fieldtype: 'Currency',
                            reqd: 1
                        },
                        {
                            label: 'Method',
                            fieldname: 'method',
                            fieldtype: 'Select',
                            options: 'By Area\nBy Market Value\nCustom Weights',
                            default: 'By Market Value',
                            reqd: 1
                        }
                    ],
                    size: 'small',
                    primary_action_label: 'Allocate',
                    primary_action(values) {
                        frappe.call({
                            method: "realestate_eg.project_structure.doctype.real_estate_project.real_estate_project.trigger_cost_allocation",
                            args: {
                                project_name: frm.doc.name,
                                cost_type: values.cost_type,
                                total_cost: flt(values.total_cost),
                                method: values.method
                            },
                            freeze: true,
                            freeze_message: __("Allocating costs across units..."),
                            callback: function(r) {
                                if(!r.exc) {
                                    frappe.show_alert({message:__("Costs allocated successfully"), indicator:'green'});
                                    frm.reload_doc();
                                }
                                d.hide();
                            }
                        });
                    }
                });
                d.show();
            }, __("Actions"));
        }
    },
});
