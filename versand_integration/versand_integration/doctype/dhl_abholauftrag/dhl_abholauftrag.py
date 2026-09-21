from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import escape_html, flt

from versand_integration.carriers.exceptions import CarrierError

STATUS_DRAFT = "Entwurf"
STATUS_PLACED = "Beauftragt"
STATUS_CANCELLED = "Storniert"
STATUS_ERROR = "Fehler"


class DHLAbholauftrag(Document):
	def validate(self):
		if not self.status:
			self.status = STATUS_DRAFT
		if flt(self.total_weight_kg) < 0:
			frappe.throw(_("Gesamtgewicht darf nicht negativ sein."))

	@frappe.whitelist()
	def place_order(self):
		"""Beauftragt den Abholauftrag bei DHL (POST /orders der Pickup API)."""
		self.check_permission("write")

		if not self.is_new():
			# Gleiche Absicherung wie Versandsendung.create_label(): Zeile
			# sperren und Status frisch aus der DB lesen, damit zwei parallele
			# Aufrufe nicht beide einen echten Abholauftrag ausloesen.
			current_status, current_order_id = frappe.db.get_value(
				self.doctype, self.name, ["status", "order_id"], for_update=True
			)
			if current_status == STATUS_PLACED and current_order_id:
				frappe.throw(
					_("Für diesen Abholauftrag existiert bereits eine Order-ID ({0}).").format(
						current_order_id
					)
				)

		from versand_integration.carriers.dhl.client import DHLClient
		from versand_integration.carriers.dhl.pickup_mapper import build_pickup_order

		settings = frappe.get_cached_doc("DHL Settings")
		payload = build_pickup_order(self, settings)
		self.api_request = json.dumps(payload, indent=2, ensure_ascii=False, default=str)

		client = DHLClient(settings)
		try:
			response = client.order_pickup(payload)
		except CarrierError as exc:
			self.status = STATUS_ERROR
			self.error_message = str(exc)
			if getattr(exc, "raw", None):
				self.api_response = json.dumps(exc.raw, indent=2, ensure_ascii=False, default=str)[:100000]
			self.save()
			frappe.db.commit()
			frappe.throw(escape_html(self.error_message), title=_("Abholauftrag fehlgeschlagen"))

		confirmation = (response.get("confirmation") or {}).get("value") or {}
		self.order_id = confirmation.get("orderID")
		self.status = STATUS_PLACED
		self.error_message = None
		self.api_response = json.dumps(response, indent=2, ensure_ascii=False, default=str)
		self.save()
		return {"order_id": self.order_id, "status": self.status}

	@frappe.whitelist()
	def cancel_pickup_order(self):
		self.check_permission("write")
		if not self.order_id:
			frappe.throw(_("Kein Order-ID vorhanden – der Abholauftrag wurde noch nicht beauftragt."))

		from versand_integration.carriers.dhl.client import DHLClient

		settings = frappe.get_cached_doc("DHL Settings")
		client = DHLClient(settings)
		try:
			result = client.cancel_pickup([self.order_id])
		except CarrierError as exc:
			frappe.throw(
				_("Stornierung fehlgeschlagen: {0}").format(escape_html(str(exc))),
				title=_("DHL Abholauftrag"),
			)
		self.status = STATUS_CANCELLED
		self.api_response = json.dumps(result, indent=2, ensure_ascii=False, default=str)
		self.save()
		return {"status": self.status}

	@frappe.whitelist()
	def refresh_pickup_status(self):
		self.check_permission("write")
		if not self.order_id:
			frappe.throw(_("Kein Order-ID vorhanden – der Abholauftrag wurde noch nicht beauftragt."))

		from versand_integration.carriers.dhl.client import DHLClient

		settings = frappe.get_cached_doc("DHL Settings")
		client = DHLClient(settings)
		try:
			orders = client.get_pickup_orders(order_id=self.order_id)
		except CarrierError as exc:
			frappe.throw(
				_("Status konnte nicht abgerufen werden: {0}").format(escape_html(str(exc))),
				title=_("DHL Abholauftrag"),
			)
		if not orders:
			frappe.msgprint(_("Keine Daten zu dieser Order-ID gefunden."))
			return {"order_state": self.order_state}

		details = orders[0].get("orderDetails") or {}
		self.order_state = details.get("orderState")
		if self.order_state == "STORNIERT":
			self.status = STATUS_CANCELLED
		self.api_response = json.dumps(orders, indent=2, ensure_ascii=False, default=str)
		self.flags.ignore_validate = True
		self.save()
		return {"order_state": self.order_state, "status": self.status}
