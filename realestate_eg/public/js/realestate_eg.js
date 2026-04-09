// Real Estate Egypt — Global Client-Side Utilities
// Version 1.0

frappe.provide("realestate_eg");

/**
 * Format Egyptian Pounds with thousands separator.
 * @param {number} amount - The amount to format.
 * @returns {string} Formatted string like "EGP 1,250,000.00"
 */
realestate_eg.format_egp = function (amount) {
    return "EGP " + (amount || 0).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
};

/**
 * Get risk level label from score.
 * @param {number} score - Risk score 0-100.
 * @returns {string} Risk level: Low, Medium, High.
 */
realestate_eg.get_risk_level = function (score) {
    if (score <= 30) return "Low";
    if (score <= 60) return "Medium";
    return "High";
};

/**
 * Get risk CSS class from score.
 * @param {number} score - Risk score 0-100.
 * @returns {string} CSS class name.
 */
realestate_eg.get_risk_class = function (score) {
    if (score <= 30) return "risk-low";
    if (score <= 60) return "risk-medium";
    return "risk-high";
};

/**
 * Show a progress bar for installment plan completion.
 * @param {HTMLElement} container - The DOM element to render into.
 * @param {number} percentage - Completion percentage (0-100).
 */
realestate_eg.render_progress = function (container, percentage) {
    const pct = Math.min(100, Math.max(0, percentage || 0));
    const cls = pct < 50 ? "warning" : "";
    $(container).html(
        `<div class="re-progress-bar">
            <div class="re-progress-fill ${cls}" style="width: ${pct}%"></div>
        </div>
        <small class="text-muted">${pct.toFixed(1)}% complete</small>`
    );
};

/**
 * Open the buyer portal in a new tab.
 */
realestate_eg.open_buyer_portal = function () {
    window.open("/buyer_portal", "_blank");
};

// ===== Custom List View Formatters =====

// Installment Plan list: color-code by status
if (frappe.listview_settings["Installment Plan"] === undefined) {
    frappe.listview_settings["Installment Plan"] = {
        get_indicator: function (doc) {
            if (doc.status === "Fully Paid") return [__("Fully Paid"), "green", "status,=,Fully Paid"];
            if (doc.status === "Active" && doc.overdue_amount > 0) return [__("Overdue"), "red", "status,=,Active"];
            if (doc.status === "Active") return [__("Active"), "blue", "status,=,Active"];
            if (doc.status === "Defaulted") return [__("Defaulted"), "red", "status,=,Defaulted"];
            if (doc.status === "Cancelled") return [__("Cancelled"), "grey", "status,=,Cancelled"];
            return [__(doc.status), "orange"];
        },
    };
}

// Post Dated Cheque list: color-code by status
if (frappe.listview_settings["Post Dated Cheque"] === undefined) {
    frappe.listview_settings["Post Dated Cheque"] = {
        get_indicator: function (doc) {
            const map = {
                "Received": ["blue"], "In Vault": ["purple"],
                "Submitted to Bank": ["orange"], "Under Collection": ["yellow"],
                "Cleared": ["green"], "Bounced": ["red"],
                "Returned to Buyer": ["grey"], "Cancelled": ["darkgrey"],
            };
            const color = (map[doc.status] || ["grey"])[0];
            return [__(doc.status), color, `status,=,${doc.status}`];
        },
    };
}

// Property Unit list: color-code by status
if (frappe.listview_settings["Property Unit"] === undefined) {
    frappe.listview_settings["Property Unit"] = {
        get_indicator: function (doc) {
            const map = {
                "Available": ["green"], "Reserved": ["blue"],
                "Under Contract": ["orange"], "Sold": ["purple"],
                "Delivered": ["darkgrey"], "Cancelled": ["red"],
            };
            const color = (map[doc.status] || ["grey"])[0];
            return [__(doc.status), color, `status,=,${doc.status}`];
        },
    };
}

// Property Contract list
if (frappe.listview_settings["Property Contract"] === undefined) {
    frappe.listview_settings["Property Contract"] = {
        get_indicator: function (doc) {
            const map = {
                "Active": ["green"], "Draft": ["orange"],
                "Fully Executed": ["blue"], "Cancelled": ["red"],
            };
            const color = (map[doc.status] || ["grey"])[0];
            return [__(doc.status), color, `status,=,${doc.status}`];
        },
    };
}
