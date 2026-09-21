"""Abholtag-Berechnung für DPD.

DPD hat keine eigene "Abholauftrag"-API - der Abholtag ergibt sich aus dem
Feld `shippingDate` (Format YYYYMMDD) im `ShipmentService`-Request selbst
(vom User anhand der DPD-API-Doku bestätigt). Setzt man z. B. das Datum von
morgen, holt DPD die Sendung morgen ab.

Bekannte Einschränkungen (ebenfalls vom User bestätigt, nicht in der PDF-
Doku dokumentiert):
- Fällt der berechnete Tag auf einen Sonntag, verschiebt DPD intern meist
  auf den nächsten Werktag (Montag) - wir machen das hier schon vorab, damit
  der tatsächlich gebuchte Tag nicht überraschend vom Feld abweicht.
- Cut-off-Zeiten fürs Depot (Anfrage für denselben Tag nur vor ca. 10-12 Uhr
  lokal) sind depotabhängig und werden hier nicht geprüft - eine Anfrage
  nach dem Cut-off wird von DPD selbst auf den nächsten Werktag verschoben
  oder abgelehnt.
"""

from __future__ import annotations

from frappe import _
from frappe.utils import add_days, getdate

from versand_integration.carriers.exceptions import CarrierConfigError

OPTION_TOMORROW = "Morgen"
OPTION_DAY_AFTER_TOMORROW = "Übermorgen"
OPTION_CUSTOM = "Wunschtag"

PICKUP_OPTIONS = [OPTION_TOMORROW, OPTION_DAY_AFTER_TOMORROW, OPTION_CUSTOM]

_SUNDAY = 6  # date.weekday(): Montag=0 ... Sonntag=6


def _shift_sunday(day):
	return add_days(day, 1) if day.weekday() == _SUNDAY else day


def resolve_shipping_date(option: str | None, custom_date=None) -> str | None:
	"""Löst 'Morgen'/'Übermorgen'/'Wunschtag' zu einem DPD-`shippingDate`
	(YYYYMMDD) auf. `None`/leere Option -> None (kein Override, DPD-Standard-
	verhalten wie bisher)."""
	if not option:
		return None
	if option == OPTION_TOMORROW:
		day = add_days(getdate(), 1)
	elif option == OPTION_DAY_AFTER_TOMORROW:
		day = add_days(getdate(), 2)
	elif option == OPTION_CUSTOM:
		if not custom_date:
			raise CarrierConfigError(_("DPD: Für 'Wunschtag' fehlt das gewünschte Datum."))
		day = getdate(custom_date)
	else:
		raise CarrierConfigError(_("DPD: unbekannte Abholtag-Option '{0}'.").format(option))
	return _shift_sunday(day).strftime("%Y%m%d")


def next_business_days(count: int, *, start=None):
	"""Liefert die nächsten `count` Werktage (Mo-Fr) ab morgen (bzw. `start`),
	Wochenenden übersprungen - Basis für die "ganze Woche"-Sammelbuchung."""
	day = add_days(start or getdate(), 1)
	days = []
	while len(days) < count:
		if day.weekday() < _SUNDAY - 1:  # 0..4 = Montag..Freitag
			days.append(day)
		day = add_days(day, 1)
	return days
