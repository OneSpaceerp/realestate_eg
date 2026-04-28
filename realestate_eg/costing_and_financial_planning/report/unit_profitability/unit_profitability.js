// Copyright (c) 2026, Nest Software Development and contributors
// For license information, please see license.txt

frappe.query_reports["Unit Profitability"] = {
	"filters": [
		{
			"fieldname": "project",
			"label": __("Project"),
			"fieldtype": "Link",
			"options": "Real Estate Project",
			"reqd": 0
		},
		{
			"fieldname": "phase",
			"label": __("Phase"),
			"fieldtype": "Link",
			"options": "Project Phase",
			"get_query": function() {
				var project = frappe.query_report.get_filter_value('project');
				if (project) {
					return {
						filters: {
							'project': project
						}
					};
				}
			}
		},
		{
			"fieldname": "status",
			"label": __("Status"),
			"fieldtype": "Select",
			"options": "\nAvailable\nReserved\nUnder Contract\nSold\nDelivered\nCancelled\nResale",
			"default": ""
		}
	]
};
