import frappe
from frappe import _
from frappe.model.document import Document

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
				_("Verbindungstest fehlgeschlagen: {0}").format(str(exc)),
				title=_("DHL Verbindungstest"),
			)
