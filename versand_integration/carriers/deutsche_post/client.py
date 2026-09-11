"""REST-Client für "Post DE Internetmarke" (DHL Developer Portal).

Ersetzt die alte SOAP/1C4A-Anbindung. Auth-Ablauf (App-Key + Portokasse-Login
-> Bearer-Token) ist von DHL bestätigt, siehe `constants.py`. Marken-Erstellung
(Warenkorb/Checkout) ist noch nicht anhand einer offiziellen Spezifikation
verifiziert – die entsprechenden Methoden werfen bewusst einen klaren Fehler
statt eine vermutete Struktur zu raten.
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
		self.username = (settings.portokasse_username or "").strip()
		self.password = (settings.get_password("portokasse_password", raise_exception=False) or "").strip()
		self._token = None

	# --------------------------------------------------------------- helpers
	def _check_config(self):
		missing = [
			label
			for label, val in (
				("Client ID", self.client_id),
				("Portokasse E-Mail", self.username),
				("Portokasse Passwort", self.password),
			)
			if not val
		]
		if missing:
			raise CarrierConfigError(
				_("Deutsche Post Settings unvollständig: {0}").format(", ".join(missing))
			)

	def _request(self, method: str, path: str, *, headers=None, json_body=None, auth: bool = True) -> dict:
		url = f"{self.base_url}{path}"
		hdrs = {"Accept": "application/json", "Content-Type": "application/json"}
		if headers:
			hdrs.update(headers)
		if auth:
			hdrs["Authorization"] = f"Bearer {self._get_token()}"
		try:
			resp = requests.request(method, url, headers=hdrs, json=json_body, timeout=_TIMEOUT)
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
				headers={
					"dhl-client-id": self.client_id,
					"Content-Type": "application/json",
					"Accept": "application/json",
				},
				json={"username": self.username, "password": self.password},
				timeout=_TIMEOUT,
			)
		except requests.RequestException as exc:
			raise CarrierAPIError(_("Internetmarke-Login nicht erreichbar: {0}").format(exc)) from exc

		if resp.status_code == 401:
			raise CarrierAPIError(
				_(
					"Internetmarke-Login: 401 Unauthorized. Häufigste Ursache: die App wurde in der "
					"Portokasse noch nicht freigegeben – auf portokasse.deutschepost.de einloggen, "
					"unter 'Meine Daten -> Geschäftsanwendungen' die Anfrage einmalig freigeben."
				),
				status_code=401,
			)
		if resp.status_code >= 400:
			raise CarrierAPIError(
				_("Internetmarke-Login HTTP {0}: {1}").format(resp.status_code, resp.text[:500]),
				status_code=resp.status_code,
			)

		body = resp.json() if resp.content else {}
		token = body.get("token") or body.get("access_token") or (resp.text or "").strip('"')
		if not token:
			raise CarrierAPIError(_("Internetmarke-Login: keine Token im Antworttext gefunden."))
		self._token = token
		return token

	# ------------------------------------------------------------ self-test
	def test_connection(self) -> dict:
		token = self._get_token()
		return {
			"ok": True,
			"messages": [
				_(
					"Bearer-Token erhalten (Client ID + Portokasse-Login akzeptiert). "
					"Marken-Erstellung selbst ist noch nicht implementiert (siehe App-Beschreibung / README)."
				)
			],
			"wallet_balance": None,
			"_token_preview": (token[:8] + "…") if token else None,
		}

	# ------------------------------------------------------- noch nicht fertig
	def retrieve_preview_voucher_pdf(self, **kwargs):
		raise CarrierConfigError(
			_(
				"Marken-Erstellung für die neue Internetmarke-REST-API ist noch nicht implementiert – "
				"es fehlt die offizielle API-Referenz für Warenkorb/Checkout. "
				"Der Button 'Verbindung testen' funktioniert bereits."
			)
		)

	def checkout_shopping_cart_pdf(self, *args, **kwargs):
		raise CarrierConfigError(
			_(
				"Marken-Erstellung für die neue Internetmarke-REST-API ist noch nicht implementiert – "
				"es fehlt die offizielle API-Referenz für Warenkorb/Checkout."
			)
		)

	def download_pdf(self, link: str) -> bytes:
		try:
			resp = requests.get(link, timeout=_TIMEOUT)
			resp.raise_for_status()
		except requests.RequestException as exc:
			raise CarrierAPIError(_("Internetmarke-PDF Download fehlgeschlagen: {0}").format(exc)) from exc
		return resp.content
