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
			"splitByParcel": False,
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
	  orderResult.shipmentResponses[].parcelInformation[].{parcelLabelNumber, output.content}
	"""
	shipment_responses = getattr(res, "shipmentResponses", None) or []
	if not isinstance(shipment_responses, list):
		shipment_responses = [shipment_responses]

	packages = []
	faults = []
	for sr in shipment_responses:
		for f in (getattr(sr, "faults", None) or []):
			faults.append(f"{getattr(f, 'faultCode', '')}: {getattr(f, 'message', f)}")
		mps_id = getattr(sr, "mpsId", None)
		parcel_infos = getattr(sr, "parcelInformation", None) or []
		if not isinstance(parcel_infos, list):
			parcel_infos = [parcel_infos]
		for pi in parcel_infos:
			output = getattr(pi, "output", None)
			content = getattr(output, "content", None) if output else None
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
	return {"packages": packages, "faults": faults, "raw": raw}
