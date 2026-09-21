"""'DHL Abholauftrag'-Dokument -> Payload für die DHL Paket DE Abholen API v3.

Schema laut offizieller OpenAPI-Spec ("DHL Parcel DE Pickup API" v3.0.0, vom
User bereitgestellt): POST /orders erwartet `PickupOrder` (siehe dortige
Beispiele Einzelabholung/Bedarfsabholung/Sonderabholung).
"""

from __future__ import annotations

from frappe import _
from frappe.utils import flt

from versand_integration.carriers.dhl.mapper import split_street
from versand_integration.carriers.exceptions import CarrierConfigError

TYPE_LOCATION = "Vereinbarter Abholort"
TYPE_ADDRESS = "Beliebige Adresse"


def _pickup_address(doc) -> dict:
	street, house = doc.street, doc.house_number
	if street and not house:
		street, house = split_street(street)
	if not (doc.name1 and street and house and doc.postal_code and doc.city):
		raise CarrierConfigError(
			_("DHL Abholauftrag: Abholadresse unvollständig (Name, Straße, Hausnummer, PLZ, Ort).")
		)
	return {
		"name1": doc.name1[:50],
		"name2": (doc.name2 or "")[:50] or None,
		"addressStreet": street[:50],
		"addressHouse": house[:8],
		"postalCode": (doc.postal_code or "").strip(),
		"city": doc.city[:44],
		# Abholaufträge sind laut Doku nur für deutsche Adressen möglich; das
		# Beispiel der Spec zeigt "DE" (alpha-2) - anders als bei /orders
		# (Shipping API), das alpha-3 (DEU) erwartet.
		"country": "DE",
	}


def build_pickup_order(doc, settings) -> dict:
	if doc.pickup_type == TYPE_LOCATION:
		if not doc.pickup_location:
			raise CarrierConfigError(_("DHL Abholauftrag: Abholort fehlt."))
		pickup_location = {"type": "Id", "asId": doc.pickup_location}
		customer_details = None
	else:
		address = _pickup_address(doc)
		address = {k: v for k, v in address.items() if v}
		pickup_location = {"type": "Address", "pickupAddress": address}
		billing_number = (doc.billing_number or settings.billing_number_pickup or "").strip()
		if not billing_number:
			raise CarrierConfigError(
				_(
					"DHL Abholauftrag: Abrechnungsnummer fehlt (Verfahren 08) – am Abholauftrag "
					"oder als Fallback in den DHL Settings hinterlegen."
				)
			)
		customer_details = {"billingNumber": billing_number}

	if doc.pickup_date_option == "So schnell wie möglich (asap)":
		pickup_date = {"type": "ASAP"}
	else:
		if not doc.pickup_date:
			raise CarrierConfigError(_("DHL Abholauftrag: Datum fehlt."))
		pickup_date = {"type": "Date", "value": str(doc.pickup_date)}

	pickup_details = {"pickupDate": pickup_date}
	if doc.comment:
		pickup_details["comment"] = doc.comment[:100]
	if flt(doc.total_weight_kg) > 0:
		pickup_details["totalWeight"] = {"uom": "kg", "value": flt(doc.total_weight_kg)}

	shipments = []
	for row in doc.shipments or []:
		shipment = {"transportationType": "PAKET"}
		if row.shipment_no:
			shipment["shipmentNo"] = row.shipment_no
		if row.size:
			shipment["size"] = row.size
		if row.customer_reference:
			shipment["customerReference"] = row.customer_reference[:20]
		shipments.append(shipment)
	if not shipments:
		# Mindestens ein Sendungs-Eintrag ist laut Spec Pflicht (minItems: 1),
		# auch wenn keine konkrete Sendungsnummer bekannt ist.
		shipments = [{"transportationType": "PAKET"}]
		if doc.pickup_type == TYPE_LOCATION:
			shipments[0]["size"] = "M"

	contact_persons = []
	if doc.contact_name or doc.contact_phone or doc.contact_email:
		contact_persons.append(
			{
				"name": (doc.contact_name or "")[:50],
				"phone": (doc.contact_phone or "")[:50],
				"email": (doc.contact_email or "")[:250],
				"emailNotification": {
					"sendPickupConfirmationEmail": bool(doc.send_confirmation_email),
					"sendPickupTimeWindowEmail": bool(doc.send_time_window_email),
				},
			}
		)

	payload = {
		"pickupLocation": pickup_location,
		"pickupDetails": pickup_details,
		"shipmentDetails": {"shipments": shipments},
	}
	if customer_details:
		payload["customerDetails"] = customer_details
	if contact_persons:
		payload["contactPerson"] = contact_persons
	return payload
