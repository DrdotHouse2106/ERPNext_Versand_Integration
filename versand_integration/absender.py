"""Einheitliche Auflösung des Versandabsenders für alle Carrier.

Reihenfolge:
1. Feld ``versandabsender`` an der Versandsendung (bzw. vom Lieferschein/Kunden geerbt)
2. Als Standard markierter ``Versandabsender``
3. Fallback: Absenderfelder im jeweiligen Carrier-Settings-Doctype
"""

from __future__ import annotations

from dataclasses import dataclass, field

import frappe
from frappe import _

from versand_integration.carriers.dhl import constants as DHL_C
from versand_integration.carriers.exceptions import CarrierConfigError


@dataclass
class ResolvedAbsender:
	source: str  # "Versandabsender:<name>" | "DHL Settings" | "DPD Settings" | "Deutsche Post Settings"
	name1: str = ""
	name2: str | None = None
	street: str | None = None
	house_number: str | None = None
	address_addition: str | None = None
	postal_code: str = ""
	city: str = ""
	country: str = "DE"
	email: str | None = None
	phone: str | None = None
	dhl_profile: str | None = None
	dhl_billing_number_return: str | None = None
	dpd_sending_depot: str | None = None
	_dhl_billing_by_code: dict = field(default_factory=dict)
	_dhl_billing_fallback: str | None = None

	def require_address(self, carrier: str):
		if not (self.name1 and self.postal_code and self.city):
			raise CarrierConfigError(
				_("Absenderadresse unvollständig (Name, PLZ, Ort) – Quelle: {0}").format(self.source)
			)

	def dhl_billing_number(self, product_code: str | None) -> str | None:
		if product_code and product_code in self._dhl_billing_by_code:
			return self._dhl_billing_by_code[product_code]
		return self._dhl_billing_fallback


def resolve(shipment) -> ResolvedAbsender:
	name = getattr(shipment, "versandabsender", None)
	if not name:
		name = frappe.db.get_value("Versandabsender", {"is_default": 1, "disabled": 0}, "name")
	if name:
		return _from_doc(frappe.get_cached_doc("Versandabsender", name))
	return _from_settings(shipment.carrier)


def _dhl_billing_from_settings() -> tuple[dict, str | None]:
	"""Globale DHL-Abrechnungsnummern: Tabelle in den DHL Settings + einfacher Fallback."""
	try:
		s = frappe.get_cached_doc("DHL Settings")
	except frappe.DoesNotExistError:
		return {}, None
	by_code = {}
	for row in getattr(s, "dhl_billing_numbers", None) or []:
		code = DHL_C.resolve_product(row.product)
		if code and row.billing_number:
			by_code[code] = row.billing_number.strip()
	return by_code, (s.billing_number or None)


def _from_doc(doc) -> ResolvedAbsender:
	# Basis: globale Nummern aus den DHL Settings, dann Marken-Overrides drüber.
	by_code, settings_fallback = _dhl_billing_from_settings()
	overrides = {}
	for row in doc.dhl_billing_numbers or []:
		code = DHL_C.resolve_product(row.product)
		if code and row.billing_number:
			overrides[code] = row.billing_number.strip()
	by_code = {**by_code, **overrides}

	return ResolvedAbsender(
		source=f"Versandabsender:{doc.name}",
		name1=doc.name1,
		name2=doc.name2,
		street=doc.street,
		house_number=doc.house_number,
		address_addition=doc.address_addition,
		postal_code=doc.postal_code,
		city=doc.city,
		country=doc.country or "DE",
		email=doc.email,
		phone=doc.phone,
		dhl_profile=doc.dhl_profile or None,
		dhl_billing_number_return=doc.dhl_billing_number_return or None,
		dpd_sending_depot=doc.dpd_sending_depot or None,
		_dhl_billing_by_code=by_code,
		_dhl_billing_fallback=next(iter(overrides.values()), None) or settings_fallback,
	)


def _from_settings(carrier: str) -> ResolvedAbsender:
	if carrier == "DPD":
		s = frappe.get_cached_doc("DPD Settings")
		return ResolvedAbsender(
			source="DPD Settings",
			name1=s.sender_name1 or "",
			name2=s.sender_name2,
			street=s.sender_street,
			house_number=s.sender_house_number,
			postal_code=s.sender_zip or "",
			city=s.sender_city or "",
			country=s.sender_country or "DE",
			email=s.sender_email,
			phone=s.sender_phone,
			dpd_sending_depot=s.sending_depot or None,
		)
	if carrier == "Deutsche Post":
		s = frappe.get_cached_doc("Deutsche Post Settings")
		return ResolvedAbsender(
			source="Deutsche Post Settings",
			name1=s.sender_name1 or "",
			name2=s.sender_name2,
			street=s.sender_street,
			house_number=s.sender_house_number,
			postal_code=s.sender_zip or "",
			city=s.sender_city or "",
			country=s.sender_country or "Deutschland",
		)

	s = frappe.get_cached_doc("DHL Settings")
	by_code, fallback = _dhl_billing_from_settings()
	return ResolvedAbsender(
		source="DHL Settings",
		name1=s.shipper_name1 or "",
		name2=s.shipper_name2,
		street=s.shipper_street,
		house_number=s.shipper_house_number,
		address_addition=s.shipper_address_addition,
		postal_code=s.shipper_postal_code or "",
		city=s.shipper_city or "",
		country=s.shipper_country or "DE",
		email=s.shipper_email,
		phone=s.shipper_phone,
		dhl_profile=s.profile or None,
		_dhl_billing_by_code=by_code,
		_dhl_billing_fallback=fallback,
	)
