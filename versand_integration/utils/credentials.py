"""Hilfsfunktionen zum Befüllen der Carrier-Settings aus lokalen JSON-Dateien.

Nutzung im Bench (self-hosted, zum Testen):

    bench --site <site> execute versand_integration.utils.credentials.load_from_file
    bench --site <site> execute versand_integration.utils.credentials.load_dpd_from_file
    bench --site <site> execute versand_integration.utils.credentials.load_dp_from_file

Gelesen wird `.secrets/<carrier>_credentials.json` im App-Verzeichnis
(per .gitignore vom Repo ausgeschlossen). Alle Schlüssel der JSON, die als
Feld im jeweiligen Settings-Doctype existieren, werden übernommen.
"""

import json
import os

import frappe


def _secrets_path(filename: str) -> str:
	app_path = frappe.get_app_path("versand_integration")
	return os.path.abspath(os.path.join(app_path, "..", ".secrets", filename))


def _load(doctype: str, filename: str, path: str | None = None):
	path = path or _secrets_path(filename)
	if not os.path.exists(path):
		frappe.throw(f"Datei nicht gefunden: {path}")

	with open(path, encoding="utf-8") as fh:
		data = json.load(fh)

	settings = frappe.get_single(doctype)
	valid_fields = {df.fieldname for df in settings.meta.fields}
	applied = []
	for key, value in data.items():
		if key in valid_fields and value not in (None, ""):
			settings.set(key, value)
			applied.append(key)

	settings.flags.ignore_permissions = True
	settings.save()
	frappe.db.commit()
	print(f"{doctype} aktualisiert ({len(applied)} Felder): {', '.join(applied)}")
	return applied


def load_from_file(path: str | None = None):
	return _load("DHL Settings", "dhl_credentials.json", path)


def load_dpd_from_file(path: str | None = None):
	return _load("DPD Settings", "dpd_credentials.json", path)


def load_dp_from_file(path: str | None = None):
	return _load("Deutsche Post Settings", "dp_credentials.json", path)
