"""Mappt ein `Versandsendung`-Dokument auf die Internetmarke-REST-Payloads.

Request-/Response-Schemas laut offizieller OpenAPI-Spec ("Deutsche Post
INTERNETMARKE API", Post & Parcel Germany) – siehe `constants.py`.
"""

from __future__ import annotations

import frappe
from frappe import _

from versand_integration.carriers.deutsche_post import constants as C
from versand_integration.carriers.dhl.mapper import to_alpha3
from versand_integration.carriers.exceptions import CarrierConfigError


def _address(name1, name2, street, house_number, postal_code, city, country) -> dict:
	postal_code = (postal_code or "").strip()
	if len(postal_code) != 5 or not postal_code.isdigit():
		raise CarrierConfigError(
			_("Internetmarke: PLZ '{0}' ist keine gültige 5-stellige deutsche PLZ.").format(postal_code)
		)
	address_line1 = " ".join(p for p in [(street or "").strip(), (house_number or "").strip()] if p)[:50]
	block = {
		"name": (name1 or "")[:50],
		"addressLine1": address_line1,
		"postalCode": postal_code,
		"city": (city or "").strip()[:40],
		"country": to_alpha3(country),
	}
	if name2:
		block["additionalName"] = name2[:40]
	return block


def sender_address(absender) -> dict:
	return _address(
		absender.name1,
		absender.name2,
		absender.street,
		absender.house_number,
		absender.postal_code,
		absender.city,
		absender.country,
	)


def receiver_address(doc) -> dict:
	return _address(
		doc.receiver_name,
		doc.receiver_name2,
		doc.receiver_street,
		doc.receiver_house_number,
		doc.receiver_postal_code,
		doc.receiver_city,
		doc.receiver_country,
	)


def product_code(doc, settings) -> int:
	"""`dp_product_code`/`default_product_code` sind Link-Felder auf 'Deutsche
	Post Produkt', deren Name direkt der numerische Produktcode ist."""
	raw = getattr(doc, "dp_product_code", None) or settings.default_product_code or C.DEFAULT_PRODUCT_CODE
	try:
		return int(raw)
	except ValueError as exc:
		raise CarrierConfigError(_("Internetmarke: Produktcode '{0}' ist keine Zahl.").format(raw)) from exc


def _voucher_layout_api(settings) -> str:
	label = settings.voucher_layout or C.DEFAULT_VOUCHER_LAYOUT
	api_value = C.VOUCHER_LAYOUT_API.get(label)
	if not api_value:
		raise CarrierConfigError(_("Internetmarke: unbekanntes Marken-Layout '{0}'.").format(label))
	return api_value


def _page_format_id(doc, settings) -> int:
	return int(getattr(doc, "dp_page_format_id", None) or settings.default_page_format_id or C.DEFAULT_PAGE_FORMAT_ID)


def build_preview_request(doc, settings) -> dict:
	"""AppShoppingCartPreviewPDFRequest – kostenlos, keine Adressen/kein Guthaben nötig."""
	body = {
		"type": "AppShoppingCartPreviewPDFRequest",
		"productCode": product_code(doc, settings),
		"voucherLayout": _voucher_layout_api(settings),
		"pageFormatId": _page_format_id(doc, settings),
	}
	image_id = settings.preview_image_id or settings.image_id
	if image_id:
		body["imageID"] = int(image_id)
	return body


def build_checkout_request(doc, settings, absender, franking_cent: int | None) -> dict:
	"""AppShoppingCartPDFRequest – echter Kauf, Portokasse wird belastet.

	`franking_cent` wird vom Carrier übergeben (Auflösung: Sendung ->
	Live-Preis aus dem Produktkatalog -> Standardbetrag in den Settings),
	damit dieser reine Payload-Builder keinen eigenen API-Zugriff braucht.
	"""
	if not franking_cent:
		raise CarrierConfigError(
			_(
				"Internetmarke (Produktiv-Modus): Frankierbetrag fehlt – weder automatisch aus dem "
				"Produktkatalog ermittelbar, noch an der Versandsendung ('Frankierbetrag (Cent)') "
				"oder als Standardbetrag in den Deutsche Post Settings hinterlegt."
			)
		)

	voucher_layout = _voucher_layout_api(settings)
	position = {
		"positionType": "AppShoppingCartPDFPosition",
		"productCode": product_code(doc, settings),
		"voucherLayout": voucher_layout,
		"position": dict(C.DEFAULT_VOUCHER_POSITION),
	}
	image_id = settings.image_id
	if image_id:
		position["imageID"] = int(image_id)
	if voucher_layout == "ADDRESS_ZONE":
		position["address"] = {
			"sender": sender_address(absender),
			"receiver": receiver_address(doc),
		}

	return {
		"type": "AppShoppingCartPDFRequest",
		"total": int(franking_cent),
		"pageFormatId": _page_format_id(doc, settings),
		"positions": [position],
	}
