# Copyright (c) 2026, Nest Software Development and contributors
# For license information, please see license.txt

"""IoT Integration — MQTT / Webhook endpoints for smart meter and sensor data."""

import frappe
from frappe import _
from frappe.utils import flt, nowdate, now_datetime
import json


@frappe.whitelist(allow_guest=True)
def sensor_data_webhook():
    """
    Webhook endpoint for IoT sensor data ingestion.
    Accepts POST data from smart meters, environmental sensors, etc.

    Expected payload:
    {
        "device_id": "METER-001",
        "sensor_type": "electricity|water|gas|temperature|humidity",
        "reading": 1234.56,
        "unit": "kWh|m3|°C|%",
        "timestamp": "2026-04-09T12:00:00Z",
        "property_unit": "PROJ-A-01-01"  // optional
    }
    """
    data = frappe.request.get_json(force=True, silent=True) or {}

    device_id = data.get("device_id")
    sensor_type = data.get("sensor_type", "electricity")
    reading = flt(data.get("reading"))
    unit = data.get("unit", "kWh")
    timestamp = data.get("timestamp", now_datetime())
    property_unit = data.get("property_unit")

    if not device_id:
        frappe.throw(_("device_id is required"), frappe.ValidationError)

    # Find associated property unit if not provided
    if not property_unit:
        property_unit = frappe.db.get_value(
            "Utility Billing",
            {"iot_sensor_id": device_id},
            "property_unit",
        )

    # Map sensor type to utility type
    type_map = {
        "electricity": "Electricity",
        "water": "Water",
        "gas": "Gas",
        "internet": "Internet",
    }
    utility_type = type_map.get(sensor_type, "Electricity")

    # Check for existing draft billing record for this period
    current_month = nowdate()[:7]  # YYYY-MM
    existing = frappe.db.get_value(
        "Utility Billing",
        {
            "property_unit": property_unit,
            "utility_type": utility_type,
            "billing_period": current_month,
            "status": "Draft",
        },
        "name",
    )

    if existing:
        # Update the end reading
        frappe.db.set_value(
            "Utility Billing",
            existing,
            {
                "meter_reading_end": reading,
                "consumption": flt(reading) - flt(
                    frappe.db.get_value("Utility Billing", existing, "meter_reading_start")
                ),
            },
        )
    else:
        # Log the reading for future reference
        frappe.get_doc(
            {
                "doctype": "Comment",
                "comment_type": "Info",
                "reference_doctype": "Property Unit",
                "reference_name": property_unit or "Unknown",
                "content": json.dumps(
                    {
                        "device_id": device_id,
                        "sensor_type": sensor_type,
                        "reading": reading,
                        "unit": unit,
                        "timestamp": str(timestamp),
                    }
                ),
            }
        ).insert(ignore_permissions=True)

    frappe.db.commit()
    return {
        "status": "ok",
        "device_id": device_id,
        "reading": reading,
        "property_unit": property_unit,
    }


@frappe.whitelist(allow_guest=True)
def device_status_webhook():
    """
    Webhook for device status updates (online/offline/error).
    """
    data = frappe.request.get_json(force=True, silent=True) or {}

    device_id = data.get("device_id")
    status = data.get("status", "online")
    battery_level = data.get("battery_level")
    signal_strength = data.get("signal_strength")

    if not device_id:
        return {"status": "error", "message": "device_id required"}

    # Log device status
    frappe.logger("realestate_eg").info(
        f"IoT device {device_id}: status={status}, battery={battery_level}%, signal={signal_strength}"
    )

    if status in ("offline", "error"):
        # Create alert for facility manager
        property_unit = frappe.db.get_value(
            "Utility Billing",
            {"iot_sensor_id": device_id},
            "property_unit",
        )

        if property_unit:
            frappe.get_doc(
                {
                    "doctype": "ToDo",
                    "description": _(
                        "IoT device {0} for unit {1} is {2}. "
                        "Battery: {3}%, Signal: {4}"
                    ).format(device_id, property_unit, status, battery_level, signal_strength),
                    "reference_type": "Property Unit",
                    "reference_name": property_unit,
                    "priority": "High" if status == "error" else "Medium",
                    "status": "Open",
                }
            ).insert(ignore_permissions=True)

    return {"status": "ok"}
