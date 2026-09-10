"""DPD-Sendungsverfolgung über den öffentlichen tracking.dpd.de-REST-Endpunkt.

Kein Login nötig. Best-effort: die Struktur ist nicht vertraglich zugesichert.
Für Sandbox-Paketnummern liegen i. d. R. keine Tracking-Daten vor.
"""

from __future__ import annotations

import requests
from frappe import _
from frappe.utils import get_datetime

from versand_integration.carriers import base
from versand_integration.carriers.exceptions import CarrierAPIError

_URL = "https://tracking.dpd.de/rest/plc/de_DE/{number}"
_TIMEOUT = 45

_KEYWORDS = (
	(base.TRACK_DELIVERED, ("zugestellt", "delivered", "empfangsberechtigt", "abgeholt vom paketshop")),
	(base.TRACK_RETURN, ("rücksendung", "retoure", "return", "an den absender")),
	(base.TRACK_OUT_FOR_DELIVERY, ("in zustellung", "zustellfahrzeug", "out for delivery", "wird heute")),
	(base.TRACK_PROBLEM, ("nicht zugestellt", "nicht möglich", "zustellhindernis", "fehlgeschlagen", "problem")),
	(base.TRACK_IN_TRANSIT, ("depot", "on the road", "unterwegs", "sortiert", "transport")),
	(base.TRACK_PICKED_UP, ("abgeholt", "übernommen", "eingeliefert", "picked up")),
	(base.TRACK_ANNOUNCED, ("auftragsdaten", "angekündigt", "order", "data")),
)


def _classify(text: str) -> str:
	t = (text or "").lower()
	for status, words in _KEYWORDS:
		if any(w in t for w in words):
			return status
	return base.TRACK_UNKNOWN


class DPDTracking:
	def track(self, tracking_number: str) -> base.TrackingResult:
		try:
			resp = requests.get(_URL.format(number=tracking_number), timeout=_TIMEOUT)
		except requests.RequestException as exc:
			raise CarrierAPIError(_("DPD-Tracking nicht erreichbar: {0}").format(exc)) from exc

		if resp.status_code == 404:
			return base.TrackingResult(status=base.TRACK_UNKNOWN, status_text=_("Noch keine Tracking-Daten."))
		if resp.status_code != 200:
			raise CarrierAPIError(_("DPD-Tracking HTTP {0}").format(resp.status_code))

		try:
			data = resp.json()
		except ValueError as exc:
			raise CarrierAPIError(_("DPD-Tracking: ungültige Antwort.")) from exc

		plc = (data.get("parcellifecycleResponse") or {}).get("parcelLifeCycleData") or {}
		status_infos = plc.get("statusInfo") or []
		events = []
		current_label = ""
		for si in status_infos:
			if not si.get("statusHasBeenReached"):
				continue
			label = si.get("label") or si.get("status") or ""
			descr = label
			d = si.get("description") or {}
			if isinstance(d, dict) and d.get("content"):
				descr = " ".join(x for x in d["content"] if x) or label
			when = _dt(si.get("date"), si.get("time"))
			events.append(
				base.TrackingEvent(
					event_time=when,
					status=si.get("status") or "",
					location=si.get("location") or "",
					description=descr,
				)
			)
			if si.get("isCurrentStatus"):
				current_label = f"{label} {descr}"
		if not current_label and events:
			current_label = events[-1].description

		events.sort(key=lambda e: e.event_time or "")
		norm = _classify(current_label)
		delivered_on = events[-1].event_time if (norm == base.TRACK_DELIVERED and events) else None
		last_update = events[-1].event_time if events else None

		return base.TrackingResult(
			status=norm,
			status_text=current_label.strip(),
			delivered_on=delivered_on,
			last_update=last_update,
			events=events,
			raw=plc,
		)


def _dt(date_str, time_str=None):
	if not date_str:
		return None
	value = f"{date_str} {time_str or '00:00'}"
	try:
		return get_datetime(value).strftime("%Y-%m-%d %H:%M:%S")
	except Exception:  # noqa: BLE001
		try:
			return get_datetime(date_str).strftime("%Y-%m-%d %H:%M:%S")
		except Exception:  # noqa: BLE001
			return None
