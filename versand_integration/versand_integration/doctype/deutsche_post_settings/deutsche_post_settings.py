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
