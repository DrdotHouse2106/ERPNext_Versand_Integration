from __future__ import annotations

import base64

import frappe
from frappe import _

from versand_integration.absender import resolve as resolve_absender
from versand_integration.carriers.base import BaseCarrier, LabelPackage, LabelResult
from versand_integration.carriers.dpd import constants as C
from versand_integration.carriers.dpd.client import DPDClient
from versand_integration.carriers.dpd.mapper import build_order


def get_dpd_settings():
	return frappe.get_cached_doc("DPD Settings")


def _b64(content) -> str | None:
	if content is None:
		return None
	if isinstance(content, bytes):
		return base64.b64encode(content).decode()
	# zeep kann base64Binary bereits als str liefern
	return str(content)


class DPDCarrier(BaseCarrier):
	name = "DPD"

	def create_label(self, shipment) -> LabelResult:
		settings = get_dpd_settings()
		absender = resolve_absender(shipment)
		client = DPDClient(settings)
		auth = client.login()

		order = build_order(settings, shipment, absender, depot=auth.get("depot"))
		result = client.store_orders(
			order,
			output_format=settings.output_format or C.DEFAULT_OUTPUT_FORMAT,
			paper_format=settings.paper_format or C.DEFAULT_PAPER_FORMAT,
		)

		pkgs = result.get("packages") or []
		if not pkgs:
			frappe.throw(_("DPD hat keine Paketdaten zurückgegeben."))

		mimetype = (
			"application/pdf"
			if (settings.output_format or C.DEFAULT_OUTPUT_FORMAT) == "PDF"
			else "text/plain"
		)
		label_packages = [
			LabelPackage(
				shipment_number=p.get("parcel_label_number"),
				tracking_number=p.get("parcel_label_number"),
				label_b64=_b64(p.get("label_bytes")),
				label_mimetype=mimetype,
			)
			for p in pkgs
		]
		main = label_packages[0]
		# Sammel-PDF: häufig hängt nur am ersten Paket das komplette Dokument.
		combined = next((lp for lp in label_packages if lp.label_b64), main)

		return LabelResult(
			shipment_number=main.shipment_number,
			tracking_number=main.tracking_number,
			tracking_url=C.TRACKING_URL_TEMPLATE.format(number=main.tracking_number),
			label_b64=combined.label_b64,
			label_mimetype=mimetype,
			packages=label_packages,
			raw_request=order,
			raw_response=result.get("raw"),
		)

	def cancel_label(self, shipment) -> dict:
		# DPD DE WebConnect kennt keinen Storno vor dem Tagesabschluss:
		# nicht abgeschlossene Sendungen werden einfach nicht übermittelt.
		return {
			"info": _(
				"DPD: Nicht manifestierte Sendungen müssen nicht storniert werden – "
				"führe den Tagesabschluss für diese Sendung einfach nicht durch."
			)
		}
