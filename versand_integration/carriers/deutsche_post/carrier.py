from __future__ import annotations

import base64

import frappe
from frappe import _

from versand_integration.carriers.base import BaseCarrier, LabelResult
from versand_integration.carriers.deutsche_post import constants as C
from versand_integration.carriers.deutsche_post.client import DPClient
from versand_integration.carriers.deutsche_post.mapper import build_positions_xml


def get_dp_settings():
	return frappe.get_cached_doc("Deutsche Post Settings")


class DeutschePostCarrier(BaseCarrier):
	"""Internetmarke (1C4A V3). BETA – noch nicht gegen echte Zugangsdaten getestet."""

	name = "Deutsche Post"

	def create_label(self, shipment) -> LabelResult:
		settings = get_dp_settings()
		client = DPClient(settings)

		auth = client.authenticate_user()
		user_token = auth.get("user_token")
		if not user_token:
			frappe.throw(_("Deutsche Post: kein userToken erhalten."))

		positions_xml, total_cent = build_positions_xml(settings, shipment)
		page_format_id = int(shipment.dp_page_format_id or settings.default_page_format_id or C.DEFAULT_PAGE_FORMAT_ID)

		result = client.checkout_shopping_cart_pdf(
			user_token,
			page_format_id=page_format_id,
			positions_xml=positions_xml,
			total_cent=total_cent,
		)

		link = result.get("link")
		if not link:
			frappe.throw(_("Deutsche Post: kein PDF-Link in der Antwort."))

		pdf = client.download_pdf(link)
		vouchers = result.get("vouchers") or []
		voucher_id = vouchers[0]["voucher_id"] if vouchers else (result.get("shop_order_id") or "IM")
		track_id = next((v.get("track_id") for v in vouchers if v.get("track_id")), None)

		return LabelResult(
			shipment_number=voucher_id,
			tracking_number=track_id or voucher_id,
			tracking_url=(
				f"https://www.deutschepost.de/sendung/simpleQuery.html?form.sendungsnummer={track_id}"
				if track_id
				else None
			),
			label_b64=base64.b64encode(pdf).decode(),
			label_mimetype="application/pdf",
			raw_request={"positions": positions_xml, "total_cent": total_cent, "pageFormatId": page_format_id},
			raw_response={
				"link": link,
				"shop_order_id": result.get("shop_order_id"),
				"wallet_balance": result.get("wallet_balance"),
				"vouchers": vouchers,
			},
		)

	def cancel_label(self, shipment) -> dict:
		# Storno/Erstattung läuft über den separaten Dienst 1C4Refund
		# (retoureVouchers) und ist hier nicht implementiert.
		return {
			"info": _(
				"Deutsche Post: Erstattung nicht genutzter Marken läuft über 1C4Refund "
				"(nicht Teil dieser App). Voucher-ID: {0}"
			).format(shipment.shipment_number or "?")
		}
