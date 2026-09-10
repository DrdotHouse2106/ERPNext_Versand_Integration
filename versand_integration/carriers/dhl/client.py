"""HTTP-Client für die DHL Parcel DE Shipping API v2."""

from __future__ import annotations

import base64
import json

import frappe
import requests
from frappe import _

from versand_integration.carriers.dhl import constants as C
from versand_integration.carriers.exceptions import CarrierAPIError, CarrierConfigError

_TOKEN_CACHE_KEY = "versand_integration:dhl:oauth_token"
_TIMEOUT = 60


class DHLClient:
	def __init__(self, settings):
		self.settings = settings
		self.sandbox = (settings.environment or "Sandbox") == "Sandbox"
		self.base_url = C.SANDBOX_BASE_URL if self.sandbox else C.PRODUCTION_BASE_URL
		self.token_url = C.SANDBOX_TOKEN_URL if self.sandbox else C.PRODUCTION_TOKEN_URL

		self.api_key = (settings.get_password("api_key", raise_exception=False) or "").strip()
		self.api_secret = (settings.get_password("api_secret", raise_exception=False) or "").strip()

		self.gkp_username = (settings.gkp_username or "").strip()
		self.gkp_password = (settings.get_password("gkp_password", raise_exception=False) or "").strip()
		if self.sandbox and not self.gkp_username:
			self.gkp_username = C.SANDBOX_GKP_USERNAME
			self.gkp_password = C.SANDBOX_GKP_PASSWORD

		self.auth_method = settings.auth_method or ("OAuth2" if self.api_secret else "Basic")
		self.print_format = settings.print_format or C.DEFAULT_PRINT_FORMAT
		self.doc_format = settings.doc_format or C.DEFAULT_DOC_FORMAT

	# ------------------------------------------------------------------ auth
	def _check_config(self):
		if not self.api_key:
			raise CarrierConfigError(_("DHL Settings: API Key fehlt."))
		if not (self.gkp_username and self.gkp_password):
			raise CarrierConfigError(
				_("DHL Settings: Geschäftskundenportal-Benutzer/Passwort fehlt.")
			)
		if self.auth_method == "OAuth2" and not self.api_secret:
			raise CarrierConfigError(_("DHL Settings: API Secret wird für OAuth2 benötigt."))

	def _oauth_token(self) -> str:
		cached = frappe.cache().get_value(_TOKEN_CACHE_KEY)
		if cached:
			return cached

		data = {
			"grant_type": "password",
			"username": self.gkp_username,
			"password": self.gkp_password,
			"client_id": self.api_key,
			"client_secret": self.api_secret,
		}
		resp = requests.post(
			self.token_url,
			data=data,
			headers={"Content-Type": "application/x-www-form-urlencoded"},
			timeout=_TIMEOUT,
		)
		if resp.status_code != 200:
			raise CarrierAPIError(
				_("DHL OAuth2-Token konnte nicht abgerufen werden (HTTP {0}).").format(
					resp.status_code
				),
				status_code=resp.status_code,
				raw=_safe_json(resp),
			)
		payload = resp.json()
		token = payload["access_token"]
		expires_in = int(payload.get("expires_in", 3600))
		frappe.cache().set_value(_TOKEN_CACHE_KEY, token, expires_in_sec=max(expires_in - 60, 60))
		return token

	def _headers(self) -> dict:
		headers = {
			"Accept": "application/json",
			"Content-Type": "application/json",
			"dhl-api-key": self.api_key,
		}
		if self.auth_method == "OAuth2":
			headers["Authorization"] = f"Bearer {self._oauth_token()}"
		else:
			raw = f"{self.gkp_username}:{self.gkp_password}".encode()
			headers["Authorization"] = "Basic " + base64.b64encode(raw).decode()
		return headers

	# ------------------------------------------------------------- requests
	def _request(self, method: str, path: str, *, params=None, json_body=None) -> dict:
		self._check_config()
		url = f"{self.base_url}{path}"
		try:
			resp = requests.request(
				method,
				url,
				params=params,
				json=json_body,
				headers=self._headers(),
				timeout=_TIMEOUT,
			)
		except requests.RequestException as exc:
			raise CarrierAPIError(_("DHL-API nicht erreichbar: {0}").format(exc)) from exc

		body = _safe_json(resp)
		if resp.status_code in (200, 201, 207):
			return body

		raise CarrierAPIError(
			_("DHL-API Fehler (HTTP {0}).").format(resp.status_code),
			status_code=resp.status_code,
			messages=_extract_messages(body),
			raw=body,
		)

	# --------------------------------------------------------------- public
	def create_orders(self, payload: dict, *, validate_only: bool = False) -> dict:
		params = {
			"includeDocs": "B64",
			"docFormat": self.doc_format,
			"printFormat": self.print_format,
			"combine": "false",
		}
		if validate_only:
			params["validate"] = "true"

		body = self._request("POST", "/orders", params=params, json_body=payload)

		# 207: pro Item prüfen
		bad = [
			it for it in body.get("items", [])
			if (it.get("sstatus") or {}).get("statusCode", 200) >= 400
		]
		if bad:
			raise CarrierAPIError(
				_("DHL hat mindestens eine Sendung abgelehnt."),
				status_code=207,
				messages=_extract_item_messages(body),
				raw=body,
			)
		return body

	def get_order(self, shipment_number: str) -> dict:
		return self._request(
			"GET",
			"/orders",
			params={
				"shipment": shipment_number,
				"includeDocs": "B64",
				"docFormat": self.doc_format,
				"printFormat": self.print_format,
			},
		)

	def cancel_order(self, shipment_number: str, profile: str) -> dict:
		return self._request(
			"DELETE",
			"/orders",
			params={"shipment": shipment_number, "profile": profile or C.DEFAULT_PROFILE},
		)

	def test_connection(self) -> dict:
		"""Validierungs-Aufruf (validate=true) mit einer Sandbox-Testsendung."""
		profile = self.settings.profile or C.DEFAULT_PROFILE
		billing = (
			self.settings.billing_number
			or C.SANDBOX_BILLING_NUMBERS["V01PAK"]
		)
		payload = {
			"profile": profile,
			"shipments": [
				{
					"product": "V01PAK",
					"billingNumber": billing,
					"refNo": "Verbindungstest",
					"shipper": {
						"name1": self.settings.shipper_name1 or "Test Absender",
						"addressStreet": self.settings.shipper_street or "Sträßchensweg",
						"addressHouse": self.settings.shipper_house_number or "10",
						"postalCode": self.settings.shipper_postal_code or "53113",
						"city": self.settings.shipper_city or "Bonn",
						"country": "DEU",
					},
					"consignee": {
						"name1": "Max Mustermann",
						"addressStreet": "Kurt-Schumacher-Str.",
						"addressHouse": "20",
						"postalCode": "53113",
						"city": "Bonn",
						"country": "DEU",
					},
					"details": {"weight": {"uom": "kg", "value": 1}},
				}
			],
		}
		body = self.create_orders(payload, validate_only=True)
		return {
			"ok": True,
			"environment": "Sandbox" if self.sandbox else "Produktion",
			"messages": _extract_item_messages(body) or ["Validierung erfolgreich."],
		}


# ---------------------------------------------------------------- helpers
def _safe_json(resp) -> dict:
	try:
		return resp.json()
	except (ValueError, json.JSONDecodeError):
		return {"_raw_text": resp.text}


def _extract_messages(body: dict) -> list[str]:
	out = []
	status = body.get("status") or {}
	if status.get("detail"):
		out.append(status["detail"])
	elif status.get("title"):
		out.append(status["title"])
	out.extend(_extract_item_messages(body))
	return out


def _extract_item_messages(body: dict) -> list[str]:
	out = []
	for item in body.get("items", []):
		for msg in item.get("validationMessages", []) or []:
			text = msg.get("validationMessage") or msg.get("property") or json.dumps(msg)
			prop = msg.get("property")
			out.append(f"{prop}: {text}" if prop and prop not in text else text)
		sstatus = item.get("sstatus") or {}
		if sstatus.get("detail"):
			out.append(sstatus["detail"])
	return out
