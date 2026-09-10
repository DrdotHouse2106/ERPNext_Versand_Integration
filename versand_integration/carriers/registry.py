import frappe
from frappe import _

from versand_integration.carriers.base import BaseCarrier

_CARRIERS = {
	"DHL": "versand_integration.carriers.dhl.carrier.DHLCarrier",
	"DPD": "versand_integration.carriers.dpd.carrier.DPDCarrier",
	"Deutsche Post": "versand_integration.carriers.deutsche_post.carrier.DeutschePostCarrier",
}


def get_carrier(name: str) -> BaseCarrier:
	path = _CARRIERS.get(name)
	if not path:
		frappe.throw(
			_("Carrier {0} wird noch nicht unterstützt. Verfügbar: {1}").format(
				name, ", ".join(_CARRIERS)
			)
		)
	cls = frappe.get_attr(path)
	return cls()


def available_carriers() -> list[str]:
	return list(_CARRIERS)
