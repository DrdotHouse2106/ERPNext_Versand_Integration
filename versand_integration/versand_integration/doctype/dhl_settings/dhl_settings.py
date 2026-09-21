import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import escape_html

from versand_integration.carriers.exceptions import CarrierError


class DHLSettings(Document):
	def validate(self):
		if self.billing_number:
			self.billing_number = self.billing_number.strip()
			if not (self.billing_number.isdigit() and len(self.billing_number) == 14):
				frappe.throw(_("Die Abrechnungsnummer muss aus genau 14 Ziffern bestehen."))

	@frappe.whitelist()
	def test_connection(self):
		from versand_integration.carriers.dhl.client import DHLClient

		try:
			return DHLClient(self).test_connection()
		except CarrierError as exc:
			frappe.throw(
				_("Verbindungstest fehlgeschlagen: {0}").format(escape_html(str(exc))),
				title=_("DHL Verbindungstest"),
			)

	@frappe.whitelist()
	def refresh_pickup_locations(self):
		"""Holt GET /locations (vereinbarte Abholorte) und spiegelt sie als
		'DHL Abholort'-Datensätze, damit sie im Abholauftrag als Link-Feld
		auswählbar sind statt roher Orts-IDs."""
		from versand_integration.carriers.dhl.client import DHLClient

		try:
			locations = DHLClient(self).get_pickup_locations()
		except CarrierError as exc:
			frappe.throw(
				_("Abholorte konnten nicht geladen werden: {0}").format(escape_html(str(exc))),
				title=_("DHL Abholorte"),
			)

		count = 0
		for loc in locations:
			location_id = loc.get("id")
			if not location_id:
				continue
			addr = loc.get("pickupAddress") or {}
			values = {
				"title": f"{addr.get('name1', '')}, {addr.get('postalCode', '')} {addr.get('city', '')}".strip(", "),
				"name1": addr.get("name1"),
				"street": addr.get("addressStreet"),
				"house_number": addr.get("addressHouse"),
				"postal_code": addr.get("postalCode"),
				"city": addr.get("city"),
			}
			if frappe.db.exists("DHL Abholort", location_id):
				frappe.db.set_value("DHL Abholort", location_id, values)
			else:
				doc = frappe.get_doc({"doctype": "DHL Abholort", "name": location_id, **values})
				doc.insert(ignore_permissions=True)
			count += 1

		return {"count": count}
