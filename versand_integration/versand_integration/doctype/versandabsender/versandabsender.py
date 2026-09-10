import frappe
from frappe import _
from frappe.model.document import Document


class Versandabsender(Document):
	def validate(self):
		self._one_default()
		for row in self.dhl_billing_numbers or []:
			bn = (row.billing_number or "").strip()
			row.billing_number = bn
			if bn and not (bn.isdigit() and len(bn) == 14):
				frappe.throw(
					_("Zeile {0}: Abrechnungsnummer muss 14 Ziffern haben.").format(row.idx)
				)

	def _one_default(self):
		if not self.is_default:
			return
		others = frappe.get_all(
			"Versandabsender",
			filters={"is_default": 1, "name": ["!=", self.name]},
			pluck="name",
		)
		for name in others:
			frappe.db.set_value("Versandabsender", name, "is_default", 0)


def get_default_absender() -> str | None:
	return frappe.db.get_value("Versandabsender", {"is_default": 1, "disabled": 0}, "name")
