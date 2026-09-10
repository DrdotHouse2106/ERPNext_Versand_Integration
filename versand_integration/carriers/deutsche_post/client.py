"""1C4A V3 SOAP-Client (Internetmarke) – schlanke, handgebaute Implementierung.

Hinweis: Diese Anbindung ist bislang **ungetestet** (kein Partnervertrag /
Portokasse-Testzugang vorhanden). Struktur nach offizieller Postman-Collection
(April 2023) und WSDL `OneClickForAppServiceV3`.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from html import escape

import frappe
import requests
from frappe import _

from versand_integration.carriers.deutsche_post import constants as C
from versand_integration.carriers.deutsche_post.signature import partner_signature, request_timestamp
from versand_integration.carriers.exceptions import CarrierAPIError, CarrierConfigError

_NS = {"soap": C.NS_SOAP, "v3": C.NS_V3}
_TIMEOUT = 60


class DPClient:
	def __init__(self, settings):
		self.settings = settings
		self.partner_id = (settings.partner_id or "").strip()
		self.key = (settings.get_password("key", raise_exception=False) or "").strip()
		self.key_phase = (settings.key_phase or "1").strip()
		self.username = (settings.portokasse_username or "").strip()
		self.password = (settings.get_password("portokasse_password", raise_exception=False) or "").strip()

	# --------------------------------------------------------------- helpers
	def _check_config(self):
		missing = [
			label
			for label, val in (
				("Partner-ID", self.partner_id),
				("Schlüssel", self.key),
				("Portokasse-Benutzer", self.username),
				("Portokasse-Passwort", self.password),
			)
			if not val
		]
		if missing:
			raise CarrierConfigError(
				_("Deutsche Post Settings unvollständig: {0}").format(", ".join(missing))
			)

	def _envelope(self, body_inner: str) -> str:
		ts = request_timestamp()
		sig = partner_signature(self.partner_id, ts, self.key_phase, self.key)
		return (
			'<?xml version="1.0" encoding="utf-8"?>'
			f'<soapenv:Envelope xmlns:soapenv="{C.NS_SOAP}" xmlns:v3="{C.NS_V3}">'
			"<soapenv:Header>"
			f"<v3:PARTNER_ID>{escape(self.partner_id)}</v3:PARTNER_ID>"
			f"<v3:REQUEST_TIMESTAMP>{ts}</v3:REQUEST_TIMESTAMP>"
			f"<v3:KEY_PHASE>{escape(self.key_phase)}</v3:KEY_PHASE>"
			f"<v3:PARTNER_SIGNATURE>{sig}</v3:PARTNER_SIGNATURE>"
			f"<v3:SIGNATURE_ALGORITHM>{C.SIGNATURE_ALGORITHM}</v3:SIGNATURE_ALGORITHM>"
			"</soapenv:Header>"
			f"<soapenv:Body>{body_inner}</soapenv:Body>"
			"</soapenv:Envelope>"
		)

	def _post(self, body_inner: str) -> ET.Element:
		self._check_config()
		envelope = self._envelope(body_inner)
		try:
			resp = requests.post(
				C.ENDPOINT,
				data=envelope.encode("utf-8"),
				headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": ""},
				timeout=_TIMEOUT,
			)
		except requests.RequestException as exc:
			raise CarrierAPIError(_("Internetmarke nicht erreichbar: {0}").format(exc)) from exc

		try:
			root = ET.fromstring(resp.text)
		except ET.ParseError as exc:
			raise CarrierAPIError(
				_("Internetmarke: ungültige Antwort (HTTP {0}).").format(resp.status_code)
			) from exc

		fault = root.find(".//soap:Fault", _NS)
		if fault is not None:
			reason = fault.findtext("faultstring") or fault.findtext(".//soap:Text", "", _NS)
			raise CarrierAPIError(_("Internetmarke-Fehler: {0}").format(reason), raw=resp.text)
		if resp.status_code >= 400:
			raise CarrierAPIError(
				_("Internetmarke HTTP {0}").format(resp.status_code), raw=resp.text
			)
		return root

	@staticmethod
	def _text(el, path):
		found = el.find(path, _NS)
		return found.text if found is not None else None

	# ---------------------------------------------------------------- calls
	def authenticate_user(self) -> dict:
		body = (
			"<v3:AuthenticateUserRequest>"
			f"<v3:username>{escape(self.username)}</v3:username>"
			f"<v3:password>{escape(self.password)}</v3:password>"
			"</v3:AuthenticateUserRequest>"
		)
		root = self._post(body)
		resp = root.find(".//v3:AuthenticateUserResponse", _NS)
		if resp is None:
			raise CarrierAPIError(_("Internetmarke: authenticateUser ohne Antwort."))
		return {
			"user_token": self._text(resp, "v3:userToken"),
			"wallet_balance": self._text(resp, "v3:walletBalance"),
			"info_message": self._text(resp, "v3:infoMessage"),
		}

	def ping(self) -> str:
		self._post("<v3:ping/>")  # wirft bei Fehler, sonst ok
		return "ok"

	def checkout_shopping_cart_pdf(
		self,
		user_token: str,
		*,
		page_format_id: int,
		positions_xml: str,
		total_cent: int,
		create_manifest: bool = False,
	) -> dict:
		body = (
			"<v3:CheckoutShoppingCartPDFRequest>"
			f"<v3:userToken>{escape(user_token)}</v3:userToken>"
			f"<v3:pageFormatId>{int(page_format_id)}</v3:pageFormatId>"
			f"{positions_xml}"
			f"<v3:total>{int(total_cent)}</v3:total>"
			f"<v3:createManifest>{'true' if create_manifest else 'false'}</v3:createManifest>"
			"<v3:createShippingList>0</v3:createShippingList>"
			"</v3:CheckoutShoppingCartPDFRequest>"
		)
		root = self._post(body)
		resp = root.find(".//v3:CheckoutShoppingCartPDFResponse", _NS)
		if resp is None:
			raise CarrierAPIError(_("Internetmarke: checkoutShoppingCartPDF ohne Antwort."), raw=ET.tostring(root, encoding="unicode"))

		vouchers = [
			{
				"voucher_id": self._text(v, "v3:voucherId"),
				"track_id": self._text(v, "v3:trackId"),
			}
			for v in resp.findall(".//v3:voucher", _NS)
		]
		return {
			"link": self._text(resp, "v3:link"),
			"shop_order_id": self._text(resp, ".//v3:shopOrderId"),
			"wallet_balance": self._text(resp, "v3:walletBalance"),
			"vouchers": vouchers,
			"raw": ET.tostring(root, encoding="unicode"),
		}

	def download_pdf(self, link: str) -> bytes:
		try:
			resp = requests.get(link, timeout=_TIMEOUT)
			resp.raise_for_status()
		except requests.RequestException as exc:
			raise CarrierAPIError(_("Internetmarke-PDF Download fehlgeschlagen: {0}").format(exc)) from exc
		return resp.content

	# ------------------------------------------------------------ self-test
	def test_connection(self) -> dict:
		auth = self.authenticate_user()
		return {
			"ok": True,
			"wallet_balance": auth.get("wallet_balance"),
			"messages": [
				_("Login ok. Portokasse-Guthaben: {0}").format(auth.get("wallet_balance") or "?")
			],
		}
