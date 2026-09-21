"""Öffentliche (whitelisted) Endpunkte für UI-Aktionen."""

import frappe
from frappe import _
from frappe.utils import cint

# Obergrenze für die Wochen-Sammelbuchung. Jeder Tag erzeugt einen echten
# Carrier-Auftrag (Kosten, bei Deutsche Post eine Portokasse-Abbuchung) -
# der Endpunkt ist whitelisted und damit auch direkt aufrufbar, nicht nur
# über den Button, der immer 5 schickt.
MAX_WEEK_SHIPMENTS = 10


@frappe.whitelist()
def create_shipment_from_delivery_note(
	delivery_note: str, create_label: int = 1, carrier: str = "DHL", versandabsender: str | None = None
):
	"""Erzeugt (oder findet) eine Versandsendung zum Lieferschein und – optional –
	direkt das Versandetikett.

	Aufruf vom Button »Versandetikett erstellen« im Lieferschein.
	"""
	if not frappe.has_permission("Delivery Note", "read", doc=delivery_note):
		frappe.throw(_("Keine Berechtigung für diesen Lieferschein."), frappe.PermissionError)

	dn = frappe.get_doc("Delivery Note", delivery_note)
	if dn.docstatus != 1:
		frappe.throw(_("Der Lieferschein muss gebucht sein."))

	# Lieferschein-Zeile bis zum Ende dieser Transaktion sperren, BEVOR wir nach
	# einer vorhandenen Versandsendung suchen. Ohne diese Sperre finden zwei
	# parallele Aufrufe (Doppelklick, zwei Tabs) beide kein `existing`, legen
	# beide eine Versandsendung an und kaufen beide ein Etikett - der
	# for_update-Schutz in Versandsendung.create_label() greift dort nicht, weil
	# es zwei verschiedene Dokumente sind.
	frappe.db.get_value("Delivery Note", delivery_note, "name", for_update=True)

	existing = frappe.db.get_value(
		"Versandsendung",
		{"delivery_note": delivery_note, "docstatus": ["<", 2]},
		"name",
	)
	if existing:
		doc = frappe.get_doc("Versandsendung", existing)
	else:
		if not frappe.has_permission("Versandsendung", "create"):
			frappe.throw(_("Keine Berechtigung, Versandsendungen anzulegen."), frappe.PermissionError)
		doc = frappe.new_doc("Versandsendung")
		doc.delivery_note = delivery_note
		doc.carrier = carrier or "DHL"
		if versandabsender:
			doc.versandabsender = versandabsender
		doc.insert()

	# doc.create_label() prueft selbst nochmal Schreibrecht (siehe
	# Versandsendung.create_label) - wichtig, weil `doc` hier auch die bereits
	# existierende Sendung eines anderen Nutzers sein kann.
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
	if not frappe.has_permission("Delivery Note", "read", doc=delivery_note):
		frappe.throw(_("Keine Berechtigung für diesen Lieferschein."), frappe.PermissionError)

	name = frappe.db.get_value(
		"Versandsendung",
		{"delivery_note": delivery_note, "docstatus": ["<", 2]},
		"name",
	)
	return name


@frappe.whitelist()
def create_week_shipments(source: str, create_label: int = 1, count: int = 5):
	"""Dupliziert eine (i. d. R. DPD-)Versandsendung für die nächsten `count`
	Werktage (Mo-Fr, Wochenende übersprungen) mit je eigenem Abholtag
	(`dpd_pickup_date`) und erstellt optional direkt die Etiketten.

	Aufruf vom Button »Für die ganze Woche buchen« an der Versandsendung.
	Ein fehlgeschlagener Tag bricht die übrigen nicht ab - jeder Tag wird
	einzeln zurückgemeldet.
	"""
	from versand_integration.carriers.dpd.pickup import next_business_days

	src = frappe.get_doc("Versandsendung", source)
	src.check_permission("read")
	if not frappe.has_permission("Versandsendung", "create"):
		frappe.throw(_("Keine Berechtigung, Versandsendungen anzulegen."), frappe.PermissionError)

	# Der Abholtag wird über DPD-Felder gesteuert (dpd_pickup_option/-date) -
	# für andere Carrier würde diese Funktion nur stumpf N Etiketten kaufen.
	if src.carrier != "DPD":
		frappe.throw(
			_("»Für die ganze Woche buchen« gibt es nur für DPD-Sendungen (diese Sendung: {0}).").format(
				src.carrier
			)
		)

	count = cint(count) or 5
	if count < 1 or count > MAX_WEEK_SHIPMENTS:
		frappe.throw(
			_("Anzahl muss zwischen 1 und {0} liegen – jeder Tag löst einen echten Versandauftrag aus.").format(
				MAX_WEEK_SHIPMENTS
			)
		)

	results = []
	for day in next_business_days(count):
		new_doc = frappe.copy_doc(src)
		new_doc.dpd_pickup_option = "Wunschtag"
		new_doc.dpd_pickup_date = day
		new_doc.insert()

		entry = {"name": new_doc.name, "date": str(day)}
		if cint(create_label):
			try:
				new_doc.create_label()
			except Exception as exc:  # noqa: BLE001 - create_label() throws ValidationError, nicht CarrierError direkt (siehe dessen eigenen Fehlerpfad)
				entry["error"] = str(exc)
		entry["status"] = new_doc.status
		entry["shipment_number"] = new_doc.shipment_number
		results.append(entry)

	return results
