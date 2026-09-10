"""Mappt ein `Versandsendung`-Dokument auf den DHL-Parcel-DE `/orders` Payload."""

from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.utils import flt

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


def _shipper_block(settings):
	if not (settings.shipper_name1 and settings.shipper_postal_code and settings.shipper_city):
		raise CarrierConfigError(
			_("Absenderadresse in den DHL Settings ist unvollständig (Name, PLZ, Ort).")
		)
	street = settings.shipper_street
	house = settings.shipper_house_number
	if street and not house:
		street, house = split_street(street)
	return _address_block(
		settings.shipper_name1,
		settings.shipper_name2,
		street,
		house,
		settings.shipper_address_addition,
		settings.shipper_postal_code,
		settings.shipper_city,
		settings.shipper_country or "DE",
		settings.shipper_email,
		settings.shipper_phone,
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


def _services(doc):
	services = {}
	if doc.service_premium:
		services["premium"] = True
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
		services["cashOnDelivery"] = {
			"amount": {"currency": doc.currency or "EUR", "value": flt(doc.cod_amount)}
		}
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


def build_order_payload(settings, doc) -> dict:
	product = doc.product or settings.default_product or "V01PAK"
	billing_number = settings.billing_number
	if not billing_number and (settings.environment or "Sandbox") == "Sandbox":
		billing_number = C.SANDBOX_BILLING_NUMBERS.get(product, C.SANDBOX_BILLING_NUMBERS["V01PAK"])
	if not billing_number:
		raise CarrierConfigError(_("Abrechnungsnummer (billingNumber) fehlt in den DHL Settings."))

	shipper = _shipper_block(settings)
	consignee = _consignee_block(doc)
	services = _services(doc)
	ref = doc.reference or doc.delivery_note or doc.name

	packages = list(doc.packages or [])
	shipments = []
	if packages:
		for pkg in packages:
			shipment = {
				"product": product,
				"billingNumber": billing_number,
				"refNo": ref[:35],
				"shipper": shipper,
				"consignee": consignee,
				"details": _details(pkg.weight_kg, pkg.length_cm, pkg.width_cm, pkg.height_cm),
			}
			if services:
				shipment["services"] = services
			shipments.append(shipment)
	else:
		shipment = {
			"product": product,
			"billingNumber": billing_number,
			"refNo": ref[:35],
			"shipper": shipper,
			"consignee": consignee,
			"details": _details(doc.total_weight, doc.length_cm, doc.width_cm, doc.height_cm),
		}
		if services:
			shipment["services"] = services
		shipments.append(shipment)

	return {"profile": settings.profile or C.DEFAULT_PROFILE, "shipments": shipments}
