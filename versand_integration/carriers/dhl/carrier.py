from __future__ import annotations

import frappe
from frappe import _

from versand_integration.absender import resolve as resolve_absender
from versand_integration.carriers.base import BaseCarrier, LabelPackage, LabelResult
from versand_integration.carriers.dhl import constants as C
from versand_integration.carriers.dhl.client import DHLClient
from versand_integration.carriers.dhl.mapper import build_order_payload


def get_dhl_settings():
	return frappe.get_cached_doc("DHL Settings")


def strip_label_data(payload):
	"""Kopie der DHL-Antwort ohne die Base64-Dokumente (label/returnLabel/codLabel).

	Wegen `includeDocs=include` enthaelt die Antwort das komplette Etikett als
	Base64. Es haengt nach `_apply_label_result()` bereits als File am Dokument -
	zusaetzlich im `api_response`-Feld waeren das je Sendung schnell mehrere
	hundert KB in `tabVersandsendung` (und in jedem Backup). Der Schluessel "b64"
	wird deshalb rekursiv durch einen Platzhalter ersetzt; alles andere (Status,
	Sendungsnummern, Validierungsmeldungen) bleibt fuer die Fehlersuche erhalten.
	"""
	if isinstance(payload, dict):
		return {
			key: (f"<{len(value)} Zeichen Base64 entfernt>" if key == "b64" and isinstance(value, str)
				else strip_label_data(value))
			for key, value in payload.items()
		}
	if isinstance(payload, list):
		return [strip_label_data(item) for item in payload]
	return payload


class DHLCarrier(BaseCarrier):
	name = "DHL"

	def create_label(self, shipment) -> LabelResult:
		settings = get_dhl_settings()
		absender = resolve_absender(shipment)
		payload = build_order_payload(settings, shipment, absender)
		client = DHLClient(settings)
		response = client.create_orders(
			payload, validate_only=bool(settings.validate_only)
		)

		items = response.get("items", [])
		if not items:
			frappe.throw(_("DHL hat keine Sendungsdaten zurückgegeben."))

		packages = []
		for it in items:
			label = it.get("label") or {}
			packages.append(
				LabelPackage(
					shipment_number=it.get("shipmentNo"),
					tracking_number=it.get("shipmentNo"),
					label_b64=label.get("b64"),
					label_mimetype="application/pdf"
					if client.doc_format == "PDF"
					else "text/plain",
				)
			)

		main = packages[0]
		return_label = (items[0].get("returnLabel") or {}) if items else {}
		return LabelResult(
			shipment_number=main.shipment_number,
			tracking_number=main.tracking_number,
			tracking_url=C.TRACKING_URL_TEMPLATE.format(number=main.tracking_number),
			label_b64=main.label_b64,
			label_mimetype=main.label_mimetype,
			packages=packages,
			raw_request=payload,
			raw_response=strip_label_data(response),
			return_label_b64=return_label.get("b64"),
			return_label_mimetype="application/pdf" if client.doc_format == "PDF" else "text/plain",
		)

	def track(self, shipment):
		from versand_integration.carriers.dhl.tracking import DHLTracking

		number = shipment.tracking_number or shipment.shipment_number
		return DHLTracking(get_dhl_settings()).track(number)

	def cancel_label(self, shipment) -> dict:
		settings = get_dhl_settings()
		client = DHLClient(settings)
		numbers = [shipment.shipment_number]
		numbers += [
			p.shipment_number for p in (shipment.packages or []) if p.shipment_number
		]
		results = {}
		for number in dict.fromkeys(n for n in numbers if n):
			results[number] = client.cancel_order(number, settings.profile)
		return results
