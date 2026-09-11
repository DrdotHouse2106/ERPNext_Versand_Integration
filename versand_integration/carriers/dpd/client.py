"""SOAP-Client für DPD DE WebConnect (via zeep)."""

from __future__ import annotations

import frappe
from frappe import _

from versand_integration.carriers.dpd import constants as C
from versand_integration.carriers.exceptions import CarrierAPIError, CarrierConfigError

_TOKEN_CACHE_PREFIX = "versand_integration:dpd:token:"


def _zeep():
	try:
		import zeep  # noqa: PLC0415
		from zeep import Settings  # noqa: PLC0415
		from zeep.transports import Transport  # noqa: PLC0415
	except ImportError as exc:  # pragma: no cover
		raise CarrierConfigError(
			_("Python-Paket 'zeep' ist nicht installiert (für DPD SOAP benötigt).")
		) from exc
	return zeep, Transport, Settings


class DPDClient:
	def __init__(self, settings):
		self.settings = settings
		self.environment = settings.environment or "Sandbox"
		self.base = C.base_url(self.environment)
		self.delis_id = (settings.delis_id or "").strip()
		self.password = (settings.get_password("password", raise_exception=False) or "").strip()
		self._auth = None  # dict: delisId, authToken, depot, customerUid

	# --------------------------------------------------------------- helpers
	def _check_config(self):
		if not (self.delis_id and self.password):
			raise CarrierConfigError(_("DPD Settings: DELIS-ID und Passwort erforderlich."))

	def _service(self, path: str):
		zeep, Transport, Settings = _zeep()
		transport = Transport(timeout=60, operation_timeout=60)
		settings = Settings(strict=False, xml_huge_tree=True)
		wsdl = f"{self.base}{path}?wsdl"
		try:
			return zeep.Client(wsdl=wsdl, transport=transport, settings=settings)
		except Exception as exc:  # noqa: BLE001
			raise CarrierAPIError(_("DPD WSDL nicht ladbar ({0}): {1}").format(wsdl, exc)) from exc

	# ----------------------------------------------------------------- login
	def _cache_key(self):
		return f"{_TOKEN_CACHE_PREFIX}{self.environment}:{self.delis_id}"

	def login(self, force: bool = False) -> dict:
		if self._auth and not force:
			return self._auth
		self._check_config()

		cached = None if force else frappe.cache().get_value(self._cache_key())
		if cached:
			self._auth = cached
			return cached

		client = self._service(C.LOGIN_SERVICE_PATH)
		try:
			res = client.service.getAuth(
				delisId=self.delis_id,
				password=self.password,
				messageLanguage=C.MESSAGE_LANGUAGE,
			)
		except Exception as exc:  # noqa: BLE001
			raise CarrierAPIError(_("DPD Login fehlgeschlagen: {0}").format(_fault(exc))) from exc

		self._auth = {
			"delisId": res.delisId or self.delis_id,
			"authToken": res.authToken,
			"depot": res.depot,
			"customerUid": getattr(res, "customerUid", None),
		}
		frappe.cache().set_value(
			self._cache_key(), self._auth, expires_in_sec=C.TOKEN_TTL_SECONDS
		)
		return self._auth

	def _auth_header(self):
		# zeep matcht den Dict-Key gegen den im WSDL deklarierten SOAP-Header
		# `authentication` (ns http://dpd.com/common/service/types/Authentication/2.0).
		auth = self.login()
		return {
			"authentication": {
				"delisId": auth["delisId"],
				"authToken": auth["authToken"],
				"messageLanguage": C.MESSAGE_LANGUAGE,
			}
		}

	# -------------------------------------------------------------- shipment
	def store_orders(self, order: dict, *, output_format: str, paper_format: str) -> dict:
		client = self._service(C.SHIPMENT_SERVICE_PATH)
		print_options = {
			"printOption": [{"outputFormat": output_format, "paperFormat": paper_format}],
			# True: jedes Paket bekommt sein eigenes Label in parcelInformation[].output
			# (passend zu unserer Paket-für-Paket-Ablage). False kombiniert alle Labels
			# einer Sendung zu einem Dokument an anderer Stelle in der Antwort.
			"splitByParcel": True,
		}
		try:
			res = client.service.storeOrders(
				_soapheaders=self._auth_header(),
				printOptions=print_options,
				order=[order],
			)
		except Exception as exc:  # noqa: BLE001
			# Auth-Token evtl. abgelaufen -> einmal neu einloggen und wiederholen.
			if not self._auth or "token" in str(exc).lower():
				frappe.cache().delete_value(self._cache_key())
				self._auth = None
				try:
					res = client.service.storeOrders(
						_soapheaders=self._auth_header(),
						printOptions=print_options,
						order=[order],
					)
				except Exception as exc2:  # noqa: BLE001
					raise CarrierAPIError(
						_("DPD storeOrders fehlgeschlagen: {0}").format(_fault(exc2))
					) from exc2
			else:
				raise CarrierAPIError(
					_("DPD storeOrders fehlgeschlagen: {0}").format(_fault(exc))
				) from exc

		return _parse_store_orders(res)


def _fault(exc) -> str:
	from zeep.exceptions import Fault  # noqa: PLC0415

	if isinstance(exc, Fault):
		return exc.message or str(exc)
	return str(exc)


def _parse_store_orders(res) -> dict:
	"""zeep-Objekt -> normalisiertes dict.

	Erwartete Struktur (ShipmentService 4.5):
	  orderResult.shipmentResponses[].parcelInformation[].{parcelLabelNumber, output[].{format, content}}

	`output` ist im WSDL wiederholbar (zeep liefert eine Liste, kein einzelnes
	Objekt) – z. B. für mehrere Dokumente/Formate pro Paket.
	"""
	shipment_responses = getattr(res, "shipmentResponses", None) or []
	if not isinstance(shipment_responses, list):
		shipment_responses = [shipment_responses]

	packages = []
	faults = []
	debug_shape = None
	for sr in shipment_responses:
		for f in (getattr(sr, "faults", None) or []):
			faults.append(f"{getattr(f, 'faultCode', '')}: {getattr(f, 'message', f)}")
		mps_id = getattr(sr, "mpsId", None)
		parcel_infos = getattr(sr, "parcelInformation", None) or []
		if not isinstance(parcel_infos, list):
			parcel_infos = [parcel_infos]
		for pi in parcel_infos:
			content = _first_output_content(getattr(pi, "output", None))
			if content is None and debug_shape is None:
				# Zur Fehlersuche: einmalig die komplette (bytes-gekürzte) Antwortstruktur
				# im api_response der Versandsendung ablegen, falls das Label mal wieder fehlt.
				debug_shape = _debug_shape(sr)
			packages.append(
				{
					"parcel_label_number": getattr(pi, "parcelLabelNumber", None) or mps_id,
					"mps_id": mps_id,
					"label_bytes": content,
				}
			)

	if faults and not packages:
		raise CarrierAPIError(_("DPD hat die Sendung abgelehnt."), messages=faults, raw={"faults": faults})

	# raw ohne Label-Bytes für das API-Protokoll auf der Versandsendung
	raw = {
		"faults": faults,
		"parcels": [
			{"parcelLabelNumber": p["parcel_label_number"], "mpsId": p["mps_id"]} for p in packages
		],
	}
	if debug_shape is not None:
		raw["debug_shape_no_label"] = debug_shape
	return {"packages": packages, "faults": faults, "raw": raw}


def _first_output_content(output):
	"""`output` ist bei zeep eine Liste von OutputType (format, content) – die erste
	mit Inhalt gewinnt."""
	if output is None:
		return None
	items = output if isinstance(output, list) else [output]
	for item in items:
		content = getattr(item, "content", None)
		if content:
			return content
	return None


def _debug_shape(obj, _depth: int = 0):
	"""zeep-Objekt bytes-sicher in JSON-taugliche Struktur wandeln (für Fehlersuche).

	Bytes/None/Primitives werden IMMER zuerst geprüft, bevor die Tiefenbegrenzung
	greift – sonst könnten rohe Label-Bytes bei tief verschachtelten Feldern
	unverkürzt durchrutschen.
	"""
	if isinstance(obj, (bytes, bytearray)):
		return f"<{len(obj)} bytes>"
	if obj is None or isinstance(obj, (str, int, float, bool)):
		return obj
	if _depth > 8:
		return f"<{type(obj).__name__}>"
	if isinstance(obj, dict):
		return {k: _debug_shape(v, _depth + 1) for k, v in obj.items()}
	if isinstance(obj, (list, tuple)):
		return [_debug_shape(v, _depth + 1) for v in list(obj)[:10]]
	values = getattr(obj, "__values__", None)
	if isinstance(values, dict):
		return {k: _debug_shape(v, _depth + 1) for k, v in values.items()}
	return str(obj)[:200]
