"""REST-Client für "Post DE Internetmarke" (DHL Developer Portal).

Ersetzt die alte SOAP/1C4A-Anbindung. Auth-Ablauf und Warenkorb-/Checkout-
Endpunkte laut offizieller OpenAPI-Spec ("Deutsche Post INTERNETMARKE API",
Post & Parcel Germany, v1.30) – live verifiziert. Dieser Client kennt keine
ERPNext-Dokumente, er nimmt fertige Payload-Dicts entgegen (gebaut von
`mapper.py`) und schickt sie roh weiter.
"""

from __future__ import annotations

import requests
from frappe import _

from versand_integration.carriers.deutsche_post import constants as C
from versand_integration.carriers.exceptions import CarrierAPIError, CarrierConfigError

_TIMEOUT = 45


class DPClient:
	def __init__(self, settings):
		self.settings = settings
		self.base_url = (settings.api_base_url or C.DEFAULT_BASE_URL).rstrip("/")
		self.client_id = (settings.get_password("client_id", raise_exception=False) or "").strip()
		self.client_secret = (settings.get_password("client_secret", raise_exception=False) or "").strip()
		self.username = (settings.portokasse_username or "").strip()
		self.password = (settings.get_password("portokasse_password", raise_exception=False) or "").strip()
		self._token = None
		self._wallet_balance = None

	# --------------------------------------------------------------- helpers
	def _check_config(self):
		missing = [
			label
			for label, val in (
				("Client ID", self.client_id),
				("Client Secret", self.client_secret),
				("Portokasse E-Mail", self.username),
				("Portokasse Passwort", self.password),
			)
			if not val
		]
		if missing:
			raise CarrierConfigError(
				_("Deutsche Post Settings unvollständig: {0}").format(", ".join(missing))
			)

	def _request(self, method: str, path: str, *, headers=None, json_body=None, params=None, auth: bool = True) -> dict:
		url = f"{self.base_url}{path}"
		hdrs = {"Accept": "application/json", "Content-Type": "application/json"}
		if headers:
			hdrs.update(headers)
		if auth:
			hdrs["Authorization"] = f"Bearer {self._get_token()}"
		try:
			resp = requests.request(method, url, headers=hdrs, json=json_body, params=params, timeout=_TIMEOUT)
		except requests.RequestException as exc:
			raise CarrierAPIError(_("Internetmarke nicht erreichbar: {0}").format(exc)) from exc

		if resp.status_code >= 400:
			raise CarrierAPIError(
				_("Internetmarke HTTP {0}: {1}").format(resp.status_code, resp.text[:500]),
				status_code=resp.status_code,
				raw={"text": resp.text[:2000]},
			)
		try:
			return resp.json()
		except ValueError:
			return {}

	# ----------------------------------------------------------------- token
	def _get_token(self) -> str:
		if self._token:
			return self._token
		self._check_config()
		url = f"{self.base_url}{C.TOKEN_PATH}"
		try:
			resp = requests.post(
				url,
				headers={"Accept": "application/json"},
				data={
					"grant_type": "client_credentials",
					"client_id": self.client_id,
					"client_secret": self.client_secret,
					"username": self.username,
					"password": self.password,
				},
				timeout=_TIMEOUT,
			)
		except requests.RequestException as exc:
			raise CarrierAPIError(_("Internetmarke-Login nicht erreichbar: {0}").format(exc)) from exc

		if resp.status_code == 401:
			raise CarrierAPIError(
				_(
					"Internetmarke-Login: 401 Unauthorized ({0}). Pruefe Client ID, Client Secret sowie "
					"Portokasse-Login. Falls DHL explizit meldet, dass die App noch nicht freigegeben "
					"ist: auf portokasse.deutschepost.de -> 'Meine Daten -> Geschäftsanwendungen' die "
					"Anfrage einmalig freigeben."
				).format(resp.text[:500]),
				status_code=401,
				raw={"text": resp.text[:2000]},
			)
		if resp.status_code >= 400:
			raise CarrierAPIError(
				_("Internetmarke-Login HTTP {0}: {1}").format(resp.status_code, resp.text[:500]),
				status_code=resp.status_code,
			)

		body = resp.json() if resp.content else {}
		token = body.get("access_token") or body.get("token") or (resp.text or "").strip('"')
		if not token:
			raise CarrierAPIError(_("Internetmarke-Login: keine Token im Antworttext gefunden."))
		self._token = token
		self._wallet_balance = body.get("walletBalance")
		return token

	# ------------------------------------------------------------ self-test
	def test_connection(self) -> dict:
		self._wallet_balance = None
		token = self._get_token()
		balance = self._wallet_balance
		balance_msg = (
			_("Portokasse-Guthaben: {0} €.").format(f"{balance / 100:.2f}")
			if balance is not None
			else ""
		)
		return {
			"ok": True,
			"messages": [
				_("Bearer-Token erhalten (Client ID/Secret + Portokasse-Login akzeptiert). {0}").format(
					balance_msg
				)
			],
			"wallet_balance": balance,
			"_token_preview": (token[:8] + "…") if token else None,
		}

	# ------------------------------------------------------- Marken-Erstellung
	def retrieve_preview_voucher_pdf(self, body: dict) -> dict:
		"""POST /app/shoppingcart/pdf?validate=true – kostenlose Vorschau, kein Portokasse-Abzug."""
		return self._request(
			"POST", C.SHOPPING_CART_PDF_PATH, json_body=body, params={"validate": "true"}
		)

	def checkout_shopping_cart_pdf(self, body: dict) -> dict:
		"""POST /app/shoppingcart/pdf?directCheckout=true – echter Kauf, Portokasse wird belastet."""
		return self._request(
			"POST", C.SHOPPING_CART_PDF_PATH, json_body=body, params={"directCheckout": "true"}
		)

	def get_catalog(self, types: list[str]) -> dict:
		"""GET /app/catalog?types=... – Motiv-/Seitenformat-/Vertragsprodukt-Katalog."""
		return self._request("GET", C.CATALOG_PATH, params={"types": types})

	def request_retoure(self, body: dict) -> dict:
		"""POST /app/retoure – Erstattung nicht genutzter Marken beantragen."""
		return self._request("POST", C.RETOURE_PATH, json_body=body)

	def download_pdf(self, link: str) -> bytes:
		try:
			resp = requests.get(link, timeout=_TIMEOUT)
			resp.raise_for_status()
		except requests.RequestException as exc:
			raise CarrierAPIError(_("Internetmarke-PDF Download fehlgeschlagen: {0}").format(exc)) from exc
		return resp.content
