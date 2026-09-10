"""Stündlicher Hintergrund-Job für die Sendungsverfolgung."""

from __future__ import annotations

import frappe
from frappe.utils import add_to_date, cint, now_datetime


def poll_open_shipments():
	"""Aktualisiert offene, gebuchte Versandsendungen mit Sendungsnummer.

	Aufruf: scheduler_events["hourly"].
	"""
	try:
		settings = frappe.get_cached_doc("Versand Integration Settings")
	except frappe.DoesNotExistError:
		return
	if not cint(settings.tracking_enabled):
		return

	min_gap_h = max(cint(settings.tracking_interval_hourly) or 1, 1)
	stale_before = add_to_date(now_datetime(), hours=-min_gap_h)
	stop_after_days = cint(settings.tracking_stop_after_days) or 21
	give_up_before = add_to_date(now_datetime(), days=-stop_after_days)

	names = frappe.get_all(
		"Versandsendung",
		filters={
			"docstatus": 1,
			"carrier": ["in", ["DHL", "DPD"]],
			"tracking_polling_active": 1,
			"shipment_number": ["is", "set"],
		},
		or_filters=[
			["tracking_last_update", "is", "not set"],
			["tracking_last_update", "<", stale_before],
		],
		pluck="name",
		limit=500,
	)

	for name in names:
		try:
			doc = frappe.get_doc("Versandsendung", name)
			if doc.creation and doc.creation < give_up_before and not doc.tracking_delivered_on:
				frappe.db.set_value(
					"Versandsendung", name, "tracking_polling_active", 0, update_modified=False
				)
				frappe.db.commit()
				continue
			doc.refresh_tracking(commit=True)
		except Exception:  # noqa: BLE001
			frappe.db.rollback()
			frappe.log_error(title=f"Tracking-Poll {name}")
