from __future__ import annotations

import base64

import frappe
from frappe import _

from versand_integration import absender as absender_mod
from versand_integration.carriers.base import BaseCarrier, LabelResult
from versand_integration.carriers.deutsche_post import constants as C
from versand_integration.carriers.deutsche_post import mapper
from versand_integration.carriers.deutsche_post.client import DPClient


def get_dp_settings():
	return frappe.get_cached_doc("Deutsche Post Settings")


class DeutschePostCarrier(BaseCarrier):
	"""Internetmarke – neue REST-API "Post DE Internetmarke" (DHL Developer Portal).

	Auth und Marken-Erstellung (Warenkorb/Checkout, PDF) laufen gegen die
	offizielle OpenAPI-Spec ("Deutsche Post INTERNETMARKE API"). Im Modus
	"Vorschau" wird nur eine kostenlose Muster-Marke geholt (kein
	Portokasse-Abzug, keine Adressen nötig); im Modus "Produktiv" wird eine
	echte Marke gekauft (Portokasse wird belastet, Frankierbetrag muss
	konfiguriert sein).
	"""

	name = "Deutsche Post"

	def create_label(self, shipment) -> LabelResult:
		settings = get_dp_settings()
		client = DPClient(settings)

		if settings.mode == C.MODE_PREVIEW:
			body = mapper.build_preview_request(shipment, settings)
			response = client.retrieve_preview_voucher_pdf(body)
		else:
			absender = absender_mod.resolve(shipment)
			absender.require_address("Deutsche Post")
			body = mapper.build_checkout_request(shipment, settings, absender)
			response = client.checkout_shopping_cart_pdf(body)

		link = response.get("link")
		if not link:
			frappe.throw(
				_("Internetmarke: Antwort enthielt keinen Link zur Marke: {0}").format(response)
			)
		label_bytes = client.download_pdf(link)

		cart = response.get("shoppingCart") or {}
		vouchers = cart.get("voucherList") or []
		voucher_id = vouchers[0].get("voucherId") if vouchers else None
		track_id = vouchers[0].get("trackId") if vouchers else None

		return LabelResult(
			shipment_number=voucher_id or f"Vorschau-{shipment.name}",
			tracking_number=track_id or "",
			tracking_url=None,
			label_b64=base64.b64encode(label_bytes).decode(),
			label_mimetype="application/pdf",
			raw_request=body,
			raw_response=response,
		)

	def cancel_label(self, shipment) -> dict:
		settings = get_dp_settings()
		raw = frappe.parse_json(shipment.api_response) if shipment.api_response else {}
		cart = (raw or {}).get("shoppingCart") or {}
		shop_order_id = cart.get("shopOrderId")
		vouchers = cart.get("voucherList") or []
		if not shop_order_id or not vouchers:
			return {
				"info": _(
					"Deutsche Post: keine Warenkorb-/Marken-Referenz gefunden (z. B. weil im "
					"Vorschau-Modus erstellt) – keine Retoure möglich. Voucher-ID: {0}"
				).format(shipment.shipment_number or "?")
			}

		client = DPClient(settings)
		body = {"shoppingCart": {"shopOrderId": shop_order_id, "voucherList": vouchers}}
		result = client.request_retoure(body)
		return {
			"info": _("Deutsche Post: Retoure beantragt (shopRetoureId {0}, Transaktion {1}).").format(
				result.get("shopRetoureId"), result.get("retoureTransactionId")
			)
		}
