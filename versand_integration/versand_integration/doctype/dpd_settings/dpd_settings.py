import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import escape_html

from versand_integration.carriers.exceptions import CarrierError


class DPDSettings(Document):
	@frappe.whitelist()
	def test_connection(self):
		# Echter Login mit den hinterlegten Zugangsdaten -> Schreibrecht.
		self.check_permission("write")

		from versand_integration.carriers.dpd.client import DPDClient

		try:
			auth = DPDClient(self).login(force=True)
		except CarrierError as exc:
			frappe.throw(
				_("DPD Login fehlgeschlagen: {0}").format(escape_html(str(exc))), title=_("DPD Verbindungstest")
			)
		return {
			"ok": True,
			"messages": [
				_("Login ok. Depot: {0}, Kunde: {1}").format(
					auth.get("depot") or "?", auth.get("customerUid") or "?"
				)
			],
		}
