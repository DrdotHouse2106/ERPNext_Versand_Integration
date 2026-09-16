"""Automatische ERPNext-Journalbuchungen für Internetmarke-Käufe/-Aufladungen.

Erzeugt normale, gebuchte `Journal Entry`-Dokumente auf dem Standard-
Kontenrahmen – kein eigenes DATEV-Format. Eine im Frappe-System bereits
installierte DATEV-Exportapp (siehe `erpnext_datev` in den App-Versionen)
kann diese Journalbuchungen regulär exportieren.

Buchungslogik (Portokasse = "Buchungskonto", ein Vorauszahlungskonto):
- Markenkauf:      Soll Gegenkonto Porto      / Haben Buchungskonto
- Aufladung:       Soll Buchungskonto         / Haben Gegenkonto Aufladung

Voraussetzung (siehe Warnhinweis in den Settings): die Portokasse wird
ausschließlich über diese App genutzt, sonst stimmt der Buchungskonto-Saldo
nicht mit dem echten Portokasse-Saldo überein.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, nowdate


def _create_journal_entry(
	*, company: str, debit_account: str, credit_account: str, amount_cent: int, user_remark: str
) -> str:
	amount = flt(amount_cent) / 100
	je = frappe.new_doc("Journal Entry")
	je.voucher_type = "Journal Entry"
	je.company = company
	je.posting_date = nowdate()
	je.user_remark = user_remark
	je.append(
		"accounts",
		{"account": debit_account, "debit_in_account_currency": amount, "credit_in_account_currency": 0},
	)
	je.append(
		"accounts",
		{"account": credit_account, "debit_in_account_currency": 0, "credit_in_account_currency": amount},
	)
	je.insert(ignore_permissions=True)
	je.submit()
	return je.name


def _check_config(settings) -> list[str]:
	missing = [
		label
		for label, val in (
			("Company", settings.datev_company),
			("Buchungskonto", settings.datev_buchungskonto),
		)
		if not val
	]
	return missing


def book_purchase(settings, *, amount_cent: int, reference: str, gegenkonto: str | None = None) -> dict:
	"""Journalbuchung für einen erfolgreichen Markenkauf.

	Wirft absichtlich NIE einen Fehler: das Geld ist zu diesem Zeitpunkt schon
	beim Carrier abgebucht, ein Fehler hier darf den bereits erfolgreichen
	Markenkauf nicht als Ganzes scheitern lassen. Bei fehlender/unvollständiger
	Konfiguration wird stattdessen ins Error Log geschrieben und
	`{"ok": False, "warning": ...}` zurückgegeben, das der Aufrufer dem Nutzer
	zusätzlich zur (weiterhin erfolgreichen) Marken-Erstellung anzeigen kann.
	"""
	if not frappe.utils.cint(settings.datev_enabled) or not amount_cent:
		return {"ok": False}
	konto = gegenkonto or settings.datev_gegenkonto_porto
	missing = _check_config(settings)
	if not konto:
		missing.append("Standardgegenkonto Porto")
	if missing:
		warning = _("Journalbuchung übersprungen – Buchhaltungs-Konfiguration unvollständig: {0}").format(
			", ".join(missing)
		)
		frappe.log_error(title="Internetmarke: Journalbuchung übersprungen (Kauf)", message=warning)
		return {"ok": False, "warning": warning}
	try:
		name = _create_journal_entry(
			company=settings.datev_company,
			debit_account=konto,
			credit_account=settings.datev_buchungskonto,
			amount_cent=amount_cent,
			user_remark=_("Internetmarke Markenkauf – {0}").format(reference),
		)
		return {"ok": True, "journal_entry": name}
	except Exception:  # noqa: BLE001
		frappe.log_error(title="Internetmarke: Journalbuchung fehlgeschlagen (Kauf)")
		return {"ok": False, "warning": _("Journalbuchung fehlgeschlagen, siehe Error Log.")}


def book_opening_balance(settings, *, amount_cent: int) -> str:
	"""Einmalige Journalbuchung für ein Guthaben, das schon vor der ersten
	Buchung über diese App in der Portokasse war. Anders als book_purchase()/
	book_topup() ist hier noch keine externe Transaktion passiert (reine
	interne Buchhaltungskorrektur) - wirft deshalb bei fehlender Konfiguration
	ganz normal einen Fehler statt nur zu warnen. Das Aufrufen dieser Funktion
	ein zweites Mal für dieselbe Settings-Instanz wird vom Aufrufer (siehe
	deutsche_post_settings.py) über `datev_opening_balance_booked` verhindert."""
	missing = _check_config(settings)
	if not settings.datev_gegenkonto_aufladung:
		missing.append("Standardaufladekonto")
	if missing:
		frappe.throw(
			_("Buchhaltungs-Konfiguration unvollständig: {0}").format(", ".join(missing))
		)
	return _create_journal_entry(
		company=settings.datev_company,
		debit_account=settings.datev_buchungskonto,
		credit_account=settings.datev_gegenkonto_aufladung,
		amount_cent=amount_cent,
		user_remark=_("Internetmarke Portokasse – Anfangsguthaben bei Aktivierung der Journalbuchungen"),
	)


def book_topup(settings, *, amount_cent: int, shop_order_id: str | None = None) -> dict:
	"""Journalbuchung für eine erfolgreiche Portokasse-Aufladung. Gleiche
	Fehlerlogik wie book_purchase(): die Aufladung selbst ist bereits
	passiert (echtes Geld), also nie hart fehlschlagen, nur warnen."""
	if not frappe.utils.cint(settings.datev_enabled) or not amount_cent:
		return {"ok": False}
	missing = _check_config(settings)
	if not settings.datev_gegenkonto_aufladung:
		missing.append("Standardaufladekonto")
	if missing:
		warning = _("Journalbuchung übersprungen – Buchhaltungs-Konfiguration unvollständig: {0}").format(
			", ".join(missing)
		)
		frappe.log_error(title="Internetmarke: Journalbuchung übersprungen (Aufladung)", message=warning)
		return {"ok": False, "warning": warning}
	try:
		name = _create_journal_entry(
			company=settings.datev_company,
			debit_account=settings.datev_buchungskonto,
			credit_account=settings.datev_gegenkonto_aufladung,
			amount_cent=amount_cent,
			user_remark=_("Internetmarke Portokasse-Aufladung{0}").format(
				f" ({shop_order_id})" if shop_order_id else ""
			),
		)
		return {"ok": True, "journal_entry": name}
	except Exception:  # noqa: BLE001
		frappe.log_error(title="Internetmarke: Journalbuchung fehlgeschlagen (Aufladung)")
		return {"ok": False, "warning": _("Journalbuchung fehlgeschlagen, siehe Error Log.")}
