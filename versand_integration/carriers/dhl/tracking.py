"""DHL Parcel DE Tracking API v0 (nur API-Key nötig, kein OAuth)."""

from __future__ import annotations

import frappe
import requests
from frappe import _
from frappe.utils import get_datetime

from versand_integration.carriers import base
from versand_integration.carriers.exceptions import CarrierAPIError, CarrierConfigError

SANDBOX_BASE = "https://api-sandbox.dhl.com/parcel/de/tracking/v0"
PRODUCTION_BASE = "https://api-eu.dhl.com/parcel/de/tracking/v0"
_TIMEOUT = 45

# statusCode der Tracking-API -> normalisierter Status
_STATUS_MAP = {
	"pre-transit": base.TRACK_ANNOUNCED,
	"transit": base.TRACK_IN_TRANSIT,
	"delivered": base.TRACK_DELIVERED,
	"failure": base.TRACK_PROBLEM,
	"unknown": base.TRACK_UNKNOWN,
}


def _refine(status: str, text: str) -> str:
	t = (text or "").lower()
	if any(w in t for w in ("zustellfahrzeug", "out for delivery", "in zustellung", "wird heute zugestellt")):
		return base.TRACK_OUT_FOR_DELIVERY
	if any(w in t for w in ("rücksendung", "retoure", "return to sender", "an den absender")):
		return base.TRACK_RETURN
	if status == base.TRACK_IN_TRANSIT and any(
		w in t for w in ("abgeholt", "picked up", "eingeliefert", "im paketzentrum")
	):
		return base.TRACK_PICKED_UP if "abgeholt" in t or "picked up" in t else status
	return status


class DHLTracking:
	def __init__(self, settings):
		sandbox = (settings.environment or "Sandbox") == "Sandbox"
		self.base_url = SANDBOX_BASE if sandbox else PRODUCTION_BASE
		self.api_key = (settings.get_password("api_key", raise_exception=False) or "").strip()

	def track(self, tracking_number: str) -> base.TrackingResult:
		if not self.api_key:
			raise CarrierConfigError(_("DHL Settings: API Key fehlt (für Tracking)."))
		try:
			resp = requests.get(
				f"{self.base_url}/shipments",
				params={"trackingNumber": tracking_number},
				headers={"dhl-api-key": self.api_key, "Accept": "application/json", "Accept-Language": "de"},
				timeout=_TIMEOUT,
			)
		except requests.RequestException as exc:
			raise CarrierAPIError(_("DHL-Tracking nicht erreichbar: {0}").format(exc)) from exc

		if resp.status_code == 404:
			return base.TrackingResult(status=base.TRACK_UNKNOWN, status_text=_("Noch keine Tracking-Daten."))
		if resp.status_code != 200:
			raise CarrierAPIError(_("DHL-Tracking HTTP {0}").format(resp.status_code), raw=_json(resp))

		body = _json(resp)
		shipments = body.get("shipments") or []
		if not shipments:
			return base.TrackingResult(status=base.TRACK_UNKNOWN, raw=body)

		sh = shipments[0]
		status_obj = sh.get("status") or {}
		norm = _STATUS_MAP.get(status_obj.get("statusCode"), base.TRACK_UNKNOWN)
		status_text = status_obj.get("description") or status_obj.get("status") or ""
		norm = _refine(norm, status_text)

		events = []
		for ev in sh.get("events") or []:
			loc = ((ev.get("location") or {}).get("address") or {}).get("addressLocality", "")
			events.append(
				base.TrackingEvent(
					event_time=_dt(ev.get("timestamp")),
					status=ev.get("status") or ev.get("statusCode") or "",
					location=loc,
					description=ev.get("description") or ev.get("status") or "",
				)
			)
		events.sort(key=lambda e: e.event_time or "")

		delivered_on = _dt(status_obj.get("timestamp")) if norm == base.TRACK_DELIVERED else None
		last_update = _dt(status_obj.get("timestamp")) or (events[-1].event_time if events else None)

		return base.TrackingResult(
			status=norm,
			status_text=status_text,
			delivered_on=delivered_on,
			last_update=last_update,
			events=events,
			raw=body,
		)


def _json(resp) -> dict:
	try:
		return resp.json()
	except ValueError:
		return {}


def _dt(value):
	if not value:
		return None
	try:
		return get_datetime(value).strftime("%Y-%m-%d %H:%M:%S")
	except Exception:  # noqa: BLE001
		return None
