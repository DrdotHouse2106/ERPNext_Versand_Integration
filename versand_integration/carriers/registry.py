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


def carriers_with_tracking() -> list[str]:
	"""Carrier, deren Klasse `supports_tracking` meldet.

	Anders als `get_carrier()` importiert das alle Carrier-Module - deshalb nur
	fuer den stuendlichen Tracking-Job gedacht, nicht fuer Request-Pfade. Spart
	dort aber eine zweite, leicht zu vergessende Liste von Carrier-Namen.
	"""
	names = []
	for name, path in _CARRIERS.items():
		try:
			cls = frappe.get_attr(path)
		except Exception:  # noqa: BLE001 - ein kaputter Carrier darf den Job nicht kippen
			frappe.log_error(title=f"Versand: Carrier {name} nicht ladbar")
			continue
		if getattr(cls, "supports_tracking", False):
			names.append(name)
	return names
