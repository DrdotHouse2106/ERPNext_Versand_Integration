from urllib.parse import urlparse

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, escape_html

from versand_integration.carriers.exceptions import CarrierError

# Nur DHL-eigene Hosts - api_base_url ist frei editierbar (Data-Feld) und wird
# u. a. mit Client Secret/Portokasse-Passwort im Body angesprochen. Ohne
# Allowlist könnte ein falsch/böswillig gesetzter Wert diese Zugangsdaten an
# einen fremden Host schicken.
_ALLOWED_API_HOST_SUFFIX = ".dhl.com"


class DeutschePostSettings(Document):
	def validate(self):
		if self.api_base_url:
			self.api_base_url = self.api_base_url.strip().rstrip("/")
			parsed = urlparse(self.api_base_url)
			host = (parsed.hostname or "").lower()
			if parsed.scheme != "https" or not (
				host == "dhl.com" or host.endswith(_ALLOWED_API_HOST_SUFFIX)
			):
				frappe.throw(
					_(
						"Basis-URL muss https:// sein und auf dhl.com liegen (z. B. "
						"https://api-eu.dhl.com/post/de/shipping/im/v1) – Client Secret und "
						"Portokasse-Passwort werden an diese Adresse gesendet."
					)
				)

	@frappe.whitelist()
	def test_connection(self):
		from versand_integration.carriers.deutsche_post.client import DPClient

		try:
			return DPClient(self).test_connection()
		except CarrierError as exc:
			frappe.throw(
				_("Verbindungstest fehlgeschlagen: {0}").format(escape_html(str(exc))),
				title=_("Internetmarke Verbindungstest"),
			)

	@frappe.whitelist()
	def refresh_catalog(self):
		"""Holt GET /app/catalog (Seitenformate, Vertragsprodukte, Motive) und
		spiegelt sie als 'Deutsche Post Seitenformat/Produkt/Motiv'-Datensätze,
		damit sie im Formular als lesbare Auswahl (Link-Felder) zur Verfügung
		stehen statt roher IDs/Codes."""
		import json

		from versand_integration.carriers.deutsche_post import catalog_sync
		from versand_integration.carriers.deutsche_post import constants as C
		from versand_integration.carriers.deutsche_post.client import DPClient

		try:
			catalog = DPClient(self).get_catalog([C.CATALOG_TYPE_PUBLIC, C.CATALOG_TYPE_PAGE_FORMATS])
		except CarrierError as exc:
			frappe.throw(
				_("Katalog konnte nicht geladen werden: {0}").format(escape_html(str(exc))),
				title=_("Internetmarke Katalog"),
			)

		# Immer ablegen (auch bei leeren Ergebnissen) - einzige Möglichkeit,
		# ohne Bench-Zugriff zu sehen, welche Top-Level-Keys die API für dieses
		# Konto tatsächlich zurückgibt, falls contractProducts/publicCatalog leer sind.
		frappe.db.set_value(
			"Deutsche Post Settings",
			"Deutsche Post Settings",
			"last_catalog_response",
			json.dumps(catalog, indent=2, ensure_ascii=False, default=str)[:100000],
		)
		frappe.db.commit()

		return catalog_sync.sync_catalog(catalog)

	@frappe.whitelist()
	def charge_wallet(self, amount_cent):
		"""PUT /app/wallet – belastet ECHTES GELD über das in der Portokasse
		hinterlegte Zahlungsmittel. Kein Sandbox-Modus dafür in der Spec."""
		self.check_permission("write")
		amount_cent = cint(amount_cent)
		if amount_cent < 1:
			frappe.throw(_("Aufladebetrag muss größer als 0 sein."))

		from versand_integration.carriers.deutsche_post import accounting
		from versand_integration.carriers.deutsche_post.client import DPClient

		try:
			result = DPClient(self).charge_wallet(amount_cent)
		except CarrierError as exc:
			frappe.throw(
				_("Aufladung fehlgeschlagen: {0}").format(escape_html(str(exc))),
				title=_("Internetmarke Portokasse aufladen"),
			)

		booking = accounting.book_topup(
			self, amount_cent=amount_cent, shop_order_id=result.get("shopOrderId")
		)
		return {
			"ok": True,
			"wallet_balance": result.get("walletBalance"),
			"shop_order_id": result.get("shopOrderId"),
			"booking_warning": booking.get("warning"),
		}

	@frappe.whitelist()
	def reconcile_wallet_balance(self):
		"""Vergleicht das echte Portokasse-Guthaben (live über die API) mit dem
		Saldo des Buchungskontos in ERPNext. Reine Kontrolle, keine Buchung -
		nützlich um zu prüfen, ob die Portokasse wirklich ausschließlich über
		diese App genutzt wurde (Voraussetzung für die automatischen
		Journalbuchungen, siehe Warnhinweis oben)."""
		if not self.datev_buchungskonto:
			frappe.throw(_("Kein Buchungskonto (Portokasse) in den Settings hinterlegt."))

		from erpnext.accounts.utils import get_balance_on

		from versand_integration.carriers.deutsche_post.client import DPClient

		try:
			live = DPClient(self).test_connection()
		except CarrierError as exc:
			frappe.throw(
				_("Guthaben konnte nicht abgerufen werden: {0}").format(escape_html(str(exc))),
				title=_("Internetmarke Saldo-Abgleich"),
			)

		live_balance_cent = live.get("wallet_balance")
		if live_balance_cent is None:
			frappe.throw(_("Die API hat kein Guthaben zurückgegeben."))

		ledger_balance = get_balance_on(account=self.datev_buchungskonto, company=self.datev_company)
		ledger_balance_cent = round(frappe.utils.flt(ledger_balance) * 100)
		diff_cent = live_balance_cent - ledger_balance_cent

		return {
			"live_balance_cent": live_balance_cent,
			"ledger_balance_cent": ledger_balance_cent,
			"diff_cent": diff_cent,
			"matches": abs(diff_cent) < 1,
		}
