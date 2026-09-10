class CarrierError(Exception):
	"""Basisklasse für alle Carrier-Fehler."""


class CarrierConfigError(CarrierError):
	"""Fehlende oder ungültige Konfiguration (Zugangsdaten, Absenderadresse …)."""


class CarrierAPIError(CarrierError):
	"""Die Carrier-API hat einen Fehler zurückgegeben.

	`messages` enthält – wenn vorhanden – die strukturierten Validierungs-/
	Fehlermeldungen des Providers, `raw` die komplette Antwort.
	"""

	def __init__(self, message, *, status_code=None, messages=None, raw=None):
		super().__init__(message)
		self.status_code = status_code
		self.messages = messages or []
		self.raw = raw
