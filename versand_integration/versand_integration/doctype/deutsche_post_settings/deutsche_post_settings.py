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
	def refresh_catalog(self):
		"""Holt GET /app/catalog (Seitenformate, Vertragsprodukte, Motive) und
		spiegelt sie als 'Deutsche Post Seitenformat/Produkt/Motiv'-Datensätze,
		damit sie im Formular als lesbare Auswahl (Link-Felder) zur Verfügung
		stehen statt roher IDs/Codes."""
		from versand_integration.carriers.deutsche_post import catalog_sync
		from versand_integration.carriers.deutsche_post import constants as C
		from versand_integration.carriers.deutsche_post.client import DPClient

		try:
			catalog = DPClient(self).get_catalog([C.CATALOG_TYPE_PUBLIC, C.CATALOG_TYPE_PAGE_FORMATS])
		except CarrierError as exc:
			frappe.throw(
				_("Katalog konnte nicht geladen werden: {0}").format(str(exc)),
				title=_("Internetmarke Katalog"),
			)

		return catalog_sync.sync_catalog(catalog)
