import frappe
from frappe import _

from versand_integration.carriers.base import BaseCarrier

# Registrierte Carrier. DPD und Deutsche Post / Portokasse sind bewusst noch
# nicht implementiert – die Architektur (BaseCarrier + LabelResult) ist aber so
# ausgelegt, dass sie hier nur ergänzt werden müssen.
_CARRIERS = {
	"DHL": "versand_integration.carriers.dhl.carrier.DHLCarrier",
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
