import frappe
from frappe import _
from frappe.model.document import Document

from versand_integration.carriers.exceptions import CarrierError


class DeutschePostSettings(Document):
	@frappe.whitelist()
	def test_connection(self):
		from versand_integration.carriers.deutsche_post.client import DPClient

		try:
			return DPClient(self).test_connection()
		except CarrierError as exc:
			frappe.throw(
				_("Verbindungstest fehlgeschlagen: {0}").format(str(exc)),
				title=_("Internetmarke Verbindungstest"),
			)

	@frappe.whitelist()
	def refresh_page_formats(self):
		"""Holt die aktuellen Seitenformate (GET /app/catalog?types=PAGE_FORMATS)
		und spiegelt sie als 'Deutsche Post Seitenformat'-Datensätze, damit sie
		im Formular als lesbare Auswahl (Link-Feld) zur Verfügung stehen."""
		from versand_integration.carriers.deutsche_post import constants as C
		from versand_integration.carriers.deutsche_post.client import DPClient

		try:
			catalog = DPClient(self).get_catalog([C.CATALOG_TYPE_PAGE_FORMATS])
		except CarrierError as exc:
			frappe.throw(
				_("Seitenformate konnten nicht geladen werden: {0}").format(str(exc)),
				title=_("Internetmarke Seitenformate"),
			)

		formats = catalog.get("pageFormats") or []
		count = 0
		for pf in formats:
			format_id = pf.get("id")
			if format_id is None:
				continue
			name = str(format_id)
			values = {
				"title": pf.get("name") or name,
				"page_type": pf.get("pageType"),
				"is_address_possible": 1 if pf.get("isAddressPossible") else 0,
				"is_image_possible": 1 if pf.get("isImagePossible") else 0,
				"description": pf.get("description"),
			}
			if frappe.db.exists("Deutsche Post Seitenformat", name):
				frappe.db.set_value("Deutsche Post Seitenformat", name, values)
			else:
				doc = frappe.get_doc({"doctype": "Deutsche Post Seitenformat", "name": name, **values})
				doc.insert(ignore_permissions=True)
			count += 1

		return {"count": count}
