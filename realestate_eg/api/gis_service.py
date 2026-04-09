# Copyright (c) 2026, Nest Software Development and contributors
# For license information, please see license.txt

"""
GIS Service — Google Maps / OpenStreetMap integration and smart meter webhooks.
"""

import frappe
from frappe import _
from frappe.utils import flt
import requests
import json


@frappe.whitelist()
def get_unit_location(unit_name: str) -> dict:
    """Get GIS coordinates and map URL for a property unit."""
    unit = frappe.get_doc("Property Unit", unit_name)
    project = frappe.get_doc("Real Estate Project", unit.project)

    return {
        "unit_name": unit.name,
        "project_name": project.project_name,
        "location": project.location,
        "gis_map_url": project.gis_map_url or "",
        "coordinates": project.get("gis_coordinates") or "",
    }


@frappe.whitelist()
def geocode_address(address: str) -> dict:
    """
    Geocode an address using the configured map provider.

    Args:
        address: Address string to geocode.

    Returns:
        Dict with lat, lng, formatted_address.
    """
    settings = _get_gis_settings()
    if not settings.get("enabled"):
        return {"status": "disabled"}

    try:
        if settings.get("provider") == "Google Maps":
            return _geocode_google(address, settings)
        else:
            return _geocode_osm(address)
    except Exception as e:
        frappe.log_error(title="Geocoding Failed", message=str(e))
        return {"status": "error", "message": str(e)}


def _geocode_google(address: str, settings: dict) -> dict:
    """Geocode using Google Maps API."""
    response = requests.get(
        "https://maps.googleapis.com/maps/api/geocode/json",
        params={"address": address, "key": settings["api_key"]},
        timeout=30,
    )
    data = response.json()
    if data.get("results"):
        location = data["results"][0]["geometry"]["location"]
        return {
            "status": "success",
            "lat": location["lat"],
            "lng": location["lng"],
            "formatted_address": data["results"][0].get("formatted_address", ""),
        }
    return {"status": "not_found"}


def _geocode_osm(address: str) -> dict:
    """Geocode using OpenStreetMap Nominatim."""
    response = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": address, "format": "json", "limit": 1},
        headers={"User-Agent": "RealEstateEG/1.0"},
        timeout=30,
    )
    data = response.json()
    if data:
        return {
            "status": "success",
            "lat": float(data[0]["lat"]),
            "lng": float(data[0]["lon"]),
            "formatted_address": data[0].get("display_name", ""),
        }
    return {"status": "not_found"}


@frappe.whitelist(allow_guest=True)
def smart_meter_webhook():
    """
    Webhook endpoint for IoT smart meter data ingestion.
    Accepts POST data from smart meters and creates/updates Utility Billing records.
    """
    data = frappe.request.get_json(force=True, silent=True) or {}

    sensor_id = data.get("sensor_id")
    reading = flt(data.get("reading"))
    utility_type = data.get("utility_type", "Electricity")
    timestamp = data.get("timestamp")

    if not sensor_id or not reading:
        frappe.throw(_("sensor_id and reading are required"), frappe.ValidationError)

    # Find the property unit associated with this sensor
    unit_name = frappe.db.get_value(
        "Utility Billing",
        {"iot_sensor_id": sensor_id},
        "property_unit",
    )

    if unit_name:
        # Update existing billing record or create new one
        frappe.get_doc(
            {
                "doctype": "Comment",
                "comment_type": "Info",
                "reference_doctype": "Property Unit",
                "reference_name": unit_name,
                "content": f"Smart meter reading: {sensor_id} = {reading} ({utility_type}) at {timestamp}",
            }
        ).insert(ignore_permissions=True)

    return {"status": "ok", "sensor_id": sensor_id, "reading": reading}


def _get_gis_settings() -> dict:
    """Get GIS settings."""
    try:
        settings = frappe.get_single("Real Estate Settings")
        return {
            "enabled": settings.get("gis_enabled") or 0,
            "provider": settings.get("gis_provider") or "OpenStreetMap",
            "api_key": settings.get("gis_api_key") or "",
        }
    except Exception:
        return {"enabled": 0}
