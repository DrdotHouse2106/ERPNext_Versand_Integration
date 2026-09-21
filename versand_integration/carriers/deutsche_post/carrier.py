from __future__ import annotations

import base64

import frappe
from frappe import _

from versand_integration import absender as absender_mod
from versand_integration.carriers.base import BaseCarrier, LabelResult
from versand_integration.carriers.deutsche_post import accounting, mapper
from versand_integration.carriers.deutsche_post import constants as C
from versand_integration.carriers.deutsche_post.client import DPClient
from versand_integration.carriers.exceptions import CarrierError


def get_dp_settings():
	return frappe.get_cached_doc("Deutsche Post Settings")


def _resolve_franking_cent(doc, settings, client) -> int | None:
	"""Auflösung Frankierbetrag: Sendungs-Override -> Live-Preis aus dem
	Produktkatalog (GET /app/catalog) -> Standardbetrag in den Settings.
	Kein Raten: kommt aus keiner Quelle ein Wert, gibt es None zurück und
	`mapper.build_checkout_request` wirft einen klaren Fehler.
	"""
	explicit = getattr(doc, "dp_franking_cent", None)
	if explicit:
		return int(explicit)

	try:
		code = mapper.product_code(doc, settings)
		catalog = client.get_catalog([C.CATALOG_TYPE_PUBLIC, C.CATALOG_TYPE_PAGE_FORMATS])
		products = ((catalog.get("contractProducts") or {}).get("products")) or []
		for product in products:
			if product.get("productCode") == code:
				price = product.get("price")
				if price:
					return int(price)
	except CarrierError:
		pass  # Katalog nicht verfügbar/kein Vertragsprodukt -> Fallback unten

	return int(settings.default_franking_cent) if settings.default_franking_cent else None


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
	# Manche Produkte (Briefe/Warensendungen mit "Basistracking") liefern eine
	# Track-ID (Voucher.trackId, landet in LabelResult.tracking_number) - die
	# erfassen wir bereits. Eine automatische Statusabfrage dafür ist aber noch
	# nicht implementiert (keine verifizierte Tracking-API-Referenz für diese
	# IDs), deshalb bleibt "Automatisch weiter verfolgen" vorerst aus.
	supports_tracking = False

	def create_label(self, shipment) -> LabelResult:
		settings = get_dp_settings()
		client = DPClient(settings)

		if settings.mode == C.MODE_PREVIEW:
			body = mapper.build_preview_request(shipment, settings)
			response = client.retrieve_preview_voucher_pdf(body)
		else:
			absender = absender_mod.resolve(shipment)
			absender.require_address("Deutsche Post")
			franking_cent = _resolve_franking_cent(shipment, settings, client)
			body = mapper.build_checkout_request(shipment, settings, absender, franking_cent)
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

		if settings.mode != C.MODE_PREVIEW:
			booking = accounting.book_purchase(
				settings, amount_cent=body.get("total"), reference=voucher_id or shipment.name
			)
			if booking.get("warning"):
				frappe.msgprint(booking["warning"], title=_("Internetmarke Buchhaltung"), indicator="orange")

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
