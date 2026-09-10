from __future__ import annotations

import frappe
from frappe import _

from versand_integration.carriers.base import BaseCarrier, LabelPackage, LabelResult
from versand_integration.carriers.dhl import constants as C
from versand_integration.carriers.dhl.client import DHLClient
from versand_integration.carriers.dhl.mapper import build_order_payload


def get_dhl_settings():
	return frappe.get_cached_doc("DHL Settings")


class DHLCarrier(BaseCarrier):
	name = "DHL"

	def create_label(self, shipment) -> LabelResult:
		settings = get_dhl_settings()
		payload = build_order_payload(settings, shipment)
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
		return LabelResult(
			shipment_number=main.shipment_number,
			tracking_number=main.tracking_number,
			tracking_url=C.TRACKING_URL_TEMPLATE.format(number=main.tracking_number),
			label_b64=main.label_b64,
			label_mimetype=main.label_mimetype,
			packages=packages,
			raw_request=payload,
			raw_response=response,
		)

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
