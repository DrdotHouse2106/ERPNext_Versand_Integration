from __future__ import annotations

import abc
from dataclasses import dataclass, field


@dataclass
class LabelPackage:
	"""Ein einzelnes Paket/Colli innerhalb einer Sendung."""

	shipment_number: str | None = None
	tracking_number: str | None = None
	label_b64: str | None = None
	label_mimetype: str = "application/pdf"


@dataclass
class LabelResult:
	"""Normalisiertes Ergebnis einer Etiketten-Erstellung – Carrier-unabhängig."""

	shipment_number: str
	tracking_number: str
	tracking_url: str | None = None
	label_b64: str | None = None
	label_mimetype: str = "application/pdf"
	packages: list[LabelPackage] = field(default_factory=list)
	raw_request: dict | None = None
	raw_response: dict | None = None


# --- Sendungsverfolgung -------------------------------------------------
# Normalisierte Status-Werte (identisch mit dem Select-Feld an der Versandsendung).
TRACK_ANNOUNCED = "Angekündigt"
TRACK_PICKED_UP = "Abgeholt"
TRACK_IN_TRANSIT = "In Transport"
TRACK_OUT_FOR_DELIVERY = "In Zustellung"
TRACK_DELIVERED = "Zugestellt"
TRACK_PROBLEM = "Zustellproblem"
TRACK_RETURN = "Retoure"
TRACK_UNKNOWN = "Unbekannt"

TRACK_FINAL = {TRACK_DELIVERED, TRACK_RETURN}


@dataclass
class TrackingEvent:
	event_time: str | None = None  # ISO-8601 / "YYYY-MM-DD HH:MM:SS"
	status: str = ""
	location: str = ""
	description: str = ""


@dataclass
class TrackingResult:
	status: str = TRACK_UNKNOWN
	status_text: str = ""
	delivered_on: str | None = None
	last_update: str | None = None
	events: list[TrackingEvent] = field(default_factory=list)
	raw: dict | None = None


class TrackingNotSupported(Exception):
	pass


class BaseCarrier(abc.ABC):
	"""Schnittstelle, die jeder Carrier (DHL, DPD, Deutsche Post …) implementiert."""

	name: str = "base"

	@abc.abstractmethod
	def create_label(self, shipment) -> LabelResult:
		"""Erstellt Versandetikett(en) für ein `Versandsendung`-Dokument."""

	@abc.abstractmethod
	def cancel_label(self, shipment) -> dict:
		"""Storniert eine bereits erstellte Sendung beim Carrier."""

	def track(self, shipment) -> TrackingResult:
		raise TrackingNotSupported(self.name)
