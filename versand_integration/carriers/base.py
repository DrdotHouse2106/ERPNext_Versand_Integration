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


class BaseCarrier(abc.ABC):
	"""Schnittstelle, die jeder Carrier (DHL, DPD, Deutsche Post …) implementiert."""

	name: str = "base"

	@abc.abstractmethod
	def create_label(self, shipment) -> LabelResult:
		"""Erstellt Versandetikett(en) für ein `Versandsendung`-Dokument."""

	@abc.abstractmethod
	def cancel_label(self, shipment) -> dict:
		"""Storniert eine bereits erstellte Sendung beim Carrier."""

	def track(self, shipment) -> dict:  # optional
		raise NotImplementedError
