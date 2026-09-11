from __future__ import annotations

import frappe
from frappe import _

from versand_integration.carriers.base import BaseCarrier, LabelResult
from versand_integration.carriers.deutsche_post.client import DPClient


def get_dp_settings():
	return frappe.get_cached_doc("Deutsche Post Settings")


class DeutschePostCarrier(BaseCarrier):
	"""Internetmarke – neue REST-API "Post DE Internetmarke" (DHL Developer Portal).

	Auth (App-Key + Portokasse-Login -> Bearer-Token) ist implementiert und über
	"Verbindung testen" prüfbar. Die eigentliche Marken-Erstellung (Warenkorb/
	Checkout) fehlt noch – es gibt dafür noch keine verifizierte API-Referenz
	(Status im Developer Portal: "Pending"). `create_label` wirft deshalb bewusst
	einen klaren Fehler statt eine geratene Anfrage zu schicken; siehe
	`client.py`/README für den aktuellen Stand.
	"""

	name = "Deutsche Post"

	def create_label(self, shipment) -> LabelResult:
		settings = get_dp_settings()
		client = DPClient(settings)
		# Wirft CarrierConfigError mit klarer Meldung ("noch nicht implementiert") –
		# der Token-Austausch selbst wird dabei bereits ausgeführt/geprüft.
		client.retrieve_preview_voucher_pdf()

	def cancel_label(self, shipment) -> dict:
		return {
			"info": _(
				"Deutsche Post: Erstattung nicht genutzter Marken ist für die neue "
				"REST-API noch nicht implementiert. Voucher-ID: {0}"
			).format(shipment.shipment_number or "?")
		}
