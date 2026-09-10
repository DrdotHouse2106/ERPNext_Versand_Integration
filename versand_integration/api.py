"""Öffentliche (whitelisted) Endpunkte für UI-Aktionen."""

import frappe
from frappe import _
from frappe.utils import cint


@frappe.whitelist()
def create_shipment_from_delivery_note(delivery_note: str, create_label: int = 1, carrier: str = "DHL"):
	"""Erzeugt (oder findet) eine Versandsendung zum Lieferschein und – optional –
	direkt das Versandetikett.

	Aufruf vom Button »Versandetikett erstellen« im Lieferschein.
	"""
	if not frappe.has_permission("Delivery Note", "read", doc=delivery_note):
		frappe.throw(_("Keine Berechtigung für diesen Lieferschein."), frappe.PermissionError)

	dn = frappe.get_doc("Delivery Note", delivery_note)
	if dn.docstatus != 1:
		frappe.throw(_("Der Lieferschein muss gebucht sein."))

	existing = frappe.db.get_value(
		"Versandsendung",
		{"delivery_note": delivery_note, "docstatus": ["<", 2]},
		"name",
	)
	if existing:
		doc = frappe.get_doc("Versandsendung", existing)
	else:
		doc = frappe.new_doc("Versandsendung")
		doc.delivery_note = delivery_note
		doc.carrier = carrier or "DHL"
		doc.insert()

	if cint(create_label) and doc.status != "Etikett erstellt":
		doc.create_label()

	return {
		"name": doc.name,
		"status": doc.status,
		"shipment_number": doc.shipment_number,
		"tracking_url": doc.tracking_url,
		"label_file": doc.label_file,
	}


@frappe.whitelist()
def get_shipment_for_delivery_note(delivery_note: str):
	name = frappe.db.get_value(
		"Versandsendung",
		{"delivery_note": delivery_note, "docstatus": ["<", 2]},
		"name",
	)
	return name
