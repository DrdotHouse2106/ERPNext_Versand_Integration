"""Hilfsfunktionen zum Befüllen der DHL Settings – z. B. für Tests.

Nutzung im Bench:

    bench --site <site> execute versand_integration.utils.credentials.load_from_file

Liest standardmäßig `.secrets/dhl_credentials.json` im App-Verzeichnis. Diese
Datei ist per .gitignore vom Repo ausgeschlossen.
"""

import json
import os

import frappe

FIELDS = (
	"environment",
	"auth_method",
	"api_key",
	"api_secret",
	"gkp_username",
	"gkp_password",
	"billing_number",
	"profile",
	"default_product",
	"print_format",
	"doc_format",
	"validate_only",
	"auto_submit",
	"shipper_name1",
	"shipper_name2",
	"shipper_street",
	"shipper_house_number",
	"shipper_address_addition",
	"shipper_postal_code",
	"shipper_city",
	"shipper_country",
	"shipper_email",
	"shipper_phone",
)


def _default_path() -> str:
	app_path = frappe.get_app_path("versand_integration")
	return os.path.abspath(os.path.join(app_path, "..", ".secrets", "dhl_credentials.json"))


def load_from_file(path: str | None = None):
	path = path or _default_path()
	if not os.path.exists(path):
		frappe.throw(f"Datei nicht gefunden: {path}")

	with open(path, encoding="utf-8") as fh:
		data = json.load(fh)

	settings = frappe.get_single("DHL Settings")
	applied = []
	for field in FIELDS:
		if field in data and data[field] not in (None, ""):
			settings.set(field, data[field])
			applied.append(field)
	settings.flags.ignore_permissions = True
	settings.save()
	frappe.db.commit()
	print(f"DHL Settings aktualisiert ({len(applied)} Felder): {', '.join(applied)}")
	return applied
