"""Mappt ein `Versandsendung`-Dokument auf den DHL-Parcel-DE `/orders` Payload."""

from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.utils import flt, today

from versand_integration.carriers.dhl import constants as C
from versand_integration.carriers.exceptions import CarrierConfigError

_STREET_RE = re.compile(r"^\s*(.*?)\s+(\d+\s*[a-zA-Z]?(?:[-/]\s*\d+\s*[a-zA-Z]?)?)\s*$")


def split_street(line: str | None) -> tuple[str, str]:
	"""'Musterstraße 12a' -> ('Musterstraße', '12a'). Fällt auf (line, '') zurück."""
	if not line:
		return "", ""
	m = _STREET_RE.match(line.strip())
	if m:
		return m.group(1).strip(), m.group(2).replace(" ", "")
	return line.strip(), ""


def to_alpha3(country: str | None) -> str:
	if not country:
		return "DEU"
	country = country.strip()
	if len(country) == 3:
		return country.upper()
	code = country.upper()
	if len(country) != 2:
		# Country-Name -> alpha-2 aus ERPNext
		code = (frappe.db.get_value("Country", country, "code") or "").upper()
	alpha3 = C.ALPHA2_TO_ALPHA3.get(code)
	if not alpha3:
		raise CarrierConfigError(
			_("Ländercode für '{0}' unbekannt. Bitte in constants.ALPHA2_TO_ALPHA3 ergänzen.").format(
				country
			)
		)
	return alpha3


def _address_block(name1, name2, street, house, addition, postal_code, city, country, email, phone):
	block = {
		"name1": (name1 or "")[:50],
		"addressStreet": (street or "")[:50],
		"postalCode": (postal_code or "").strip(),
		"city": (city or "").strip(),
		"country": to_alpha3(country),
	}
	if name2:
		block["name2"] = name2[:50]
	if house:
		block["addressHouse"] = house[:10]
	if addition:
		block["additionalAddressInformation1"] = addition[:60]
	if email:
		block["email"] = email
	if phone:
		block["phone"] = phone
	return block


def _shipper_block(absender):
	absender.require_address("DHL")
	street = absender.street
	house = absender.house_number
	if street and not house:
		street, house = split_street(street)
	return _address_block(
		absender.name1,
		absender.name2,
		street,
		house,
		absender.address_addition,
		absender.postal_code,
		absender.city,
		absender.country or "DE",
		absender.email,
		absender.phone,
	)


def _consignee_block(doc):
	street = doc.receiver_street
	house = doc.receiver_house_number
	if street and not house:
		street, house = split_street(street)
	return _address_block(
		doc.receiver_name,
		doc.receiver_name2,
		street,
		house,
		doc.receiver_address_addition,
		doc.receiver_postal_code,
		doc.receiver_city,
		doc.receiver_country or "DE",
		doc.receiver_email,
		doc.receiver_phone,
	)


INTERNATIONAL_PRODUCTS = {"V53WPAK", "V54EPAK", "V66WPI"}


def _services(doc, settings, product_code):
	services = {}

	premium = bool(doc.service_premium)
	if (
		not premium
		and getattr(settings, "default_premium_international", 0)
		and product_code in INTERNATIONAL_PRODUCTS
	):
		premium = True
	if premium:
		services["premium"] = True

	if doc.service_gogreen_plus or getattr(settings, "default_gogreen_plus", 0):
		services["goGreenPlus"] = True

	if doc.service_bulky_goods:
		services["bulkyGoods"] = True
	if doc.service_named_person_only:
		services["namedPersonOnly"] = True
	if doc.service_signed_for_by_recipient:
		services["signedForByRecipient"] = True
	if doc.service_no_neighbour_delivery:
		services["noNeighbourDelivery"] = True
	if doc.service_visual_check_of_age:
		services["visualCheckOfAge"] = doc.service_visual_check_of_age
	if flt(doc.cod_amount) > 0:
		# transferNote1 ist Pflicht. Bankdaten kommen aus dem GKP-Profil
		# (Standard-accountReference), sofern keine explizit hinterlegt ist.
		cod = {
			"amount": {"currency": "EUR", "value": flt(doc.cod_amount)},
			"transferNote1": (doc.reference or doc.name or "")[:35],
		}
		if getattr(doc, "cod_account_reference", None):
			cod["accountReference"] = doc.cod_account_reference
		services["cashOnDelivery"] = cod
	return services


def _details(weight_kg, length_cm, width_cm, height_cm):
	details = {"weight": {"uom": "kg", "value": round(flt(weight_kg), 3)}}
	if length_cm and width_cm and height_cm:
		details["dim"] = {
			"uom": "cm",
			"length": int(round(flt(length_cm))),
			"width": int(round(flt(width_cm))),
			"height": int(round(flt(height_cm))),
		}
	return details


def build_order_payload(settings, doc, absender) -> dict:
	product = C.resolve_product(doc.product or settings.default_product) or "V01PAK"

	billing_number = absender.dhl_billing_number(product)
	if not billing_number and (settings.environment or "Sandbox") == "Sandbox":
		billing_number = C.SANDBOX_BILLING_NUMBERS.get(product, C.SANDBOX_BILLING_NUMBERS["V01PAK"])
	if not billing_number:
		raise CarrierConfigError(
			_("Keine DHL-Abrechnungsnummer für Produkt '{0}' – bitte im Versandabsender '{1}' hinterlegen.").format(
				C.product_label(product), absender.source
			)
		)

	shipper = _shipper_block(absender)
	consignee = _consignee_block(doc)
	services = _services(doc, settings, product)
	ship_date = today()
	profile = absender.dhl_profile or settings.profile or C.DEFAULT_PROFILE

	# refNo: DHL verlangt 8–35 Zeichen; darunter lieber weglassen.
	ref = (doc.reference or doc.delivery_note or doc.name or "").strip()[:35]
	ref_no = ref if len(ref) >= 8 else None

	def _base_shipment(details):
		shipment = {
			"product": product,
			"billingNumber": billing_number,
			"shipDate": ship_date,
			"shipper": shipper,
			"consignee": consignee,
			"details": details,
		}
		if ref_no:
			shipment["refNo"] = ref_no
		if services:
			shipment["services"] = services
		return shipment

	packages = list(doc.packages or [])
	if packages:
		shipments = [
			_base_shipment(_details(p.weight_kg, p.length_cm, p.width_cm, p.height_cm))
			for p in packages
		]
	else:
		shipments = [
			_base_shipment(
				_details(doc.total_weight, doc.length_cm, doc.width_cm, doc.height_cm)
			)
		]

	return {"profile": profile, "shipments": shipments}
