"""Versandsendung -> DPD storeOrders `order`-Struktur."""

from __future__ import annotations

from frappe import _
from frappe.utils import flt

from versand_integration.carriers.dpd import constants as C
from versand_integration.carriers.exceptions import CarrierConfigError


def _weight_10g(weight_kg) -> int:
	"""DPD-Gewicht: Gramm auf 10 g gerundet, ohne Dezimalpunkt (300 = 3 kg)."""
	return max(1, int(round(flt(weight_kg) * 100)))


def _address(name1, name2, street, house_no, country, zip_code, city, state=None, email=None, phone=None):
	block = {
		"name1": (name1 or "")[:50],
		"street": (street or "")[:50],
		"country": _country(country),
		"zipCode": (zip_code or "").replace(" ", "")[:9],
		"city": (city or "")[:50],
	}
	if name2:
		block["name2"] = name2[:50]
	if house_no:
		block["houseNo"] = str(house_no)[:8]
	if state:
		block["state"] = state[:2]
	if email:
		block["email"] = email[:100]
	if phone:
		block["phone"] = phone[:30]
	return block


def _country(value) -> str:
	if not value:
		return "DE"
	value = value.strip()
	if len(value) == 2:
		return value.upper()
	import frappe  # noqa: PLC0415

	code = frappe.db.get_value("Country", value, "code")
	if not code:
		raise CarrierConfigError(_("DPD: Ländercode für '{0}' unbekannt.").format(value))
	return code.upper()


def _sender(settings):
	if not (settings.sender_name1 and settings.sender_zip and settings.sender_city):
		raise CarrierConfigError(_("DPD Settings: Absenderadresse unvollständig (Name, PLZ, Ort)."))
	return _address(
		settings.sender_name1,
		settings.sender_name2,
		settings.sender_street,
		settings.sender_house_number,
		settings.sender_country or "DE",
		settings.sender_zip,
		settings.sender_city,
		email=settings.sender_email,
		phone=settings.sender_phone,
	)


def build_order(settings, doc, depot: str) -> dict:
	product = (doc.product_override or settings.default_product or C.DEFAULT_PRODUCT).strip()
	sending_depot = (settings.sending_depot or depot or "").strip()
	if not sending_depot:
		raise CarrierConfigError(_("DPD: sendingDepot fehlt (kommt normalerweise aus dem Login)."))

	recipient = _address(
		doc.receiver_name,
		doc.receiver_name2,
		doc.receiver_street,
		doc.receiver_house_number,
		doc.receiver_country or "DE",
		doc.receiver_postal_code,
		doc.receiver_city,
		email=doc.receiver_email,
		phone=doc.receiver_phone,
	)

	packages = list(doc.packages or [])
	if packages:
		parcels = [{"weight": _weight_10g(p.weight_kg)} for p in packages]
	else:
		parcels = [{"weight": _weight_10g(doc.total_weight)}]

	general = {
		"sendingDepot": sending_depot,
		"product": product,
		"sender": _sender(settings),
		"recipient": recipient,
		"softwareVersion": C.SOFTWARE_VERSION,
	}
	ref = (doc.reference or doc.delivery_note or doc.name or "").strip()
	if ref:
		general["mpsCustomerReferenceNumber1"] = ref[:35]

	return {
		"generalShipmentData": general,
		"parcels": parcels,
		"productAndServiceData": {"orderType": C.ORDER_TYPE},
	}
