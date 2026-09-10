import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CUSTOM_FIELDS = {
	"Delivery Note": [
		{
			"fieldname": "vi_versand_section",
			"label": "Versand / Versandetikett",
			"fieldtype": "Section Break",
			"insert_after": "customer_name",
			"collapsible": 1,
		},
		{
			"fieldname": "vi_versandsendung",
			"label": "Versandsendung",
			"fieldtype": "Link",
			"options": "Versandsendung",
			"insert_after": "vi_versand_section",
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "vi_column_break_versand",
			"fieldtype": "Column Break",
			"insert_after": "vi_versandsendung",
		},
		{
			"fieldname": "vi_sendungsnummer",
			"label": "Sendungsnummer",
			"fieldtype": "Data",
			"insert_after": "vi_column_break_versand",
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "vi_tracking_url",
			"label": "Sendungsverfolgung",
			"fieldtype": "Data",
			"options": "URL",
			"insert_after": "vi_sendungsnummer",
			"read_only": 1,
			"no_copy": 1,
		},
	]
}


SINGLETONS = ("DHL Settings", "DPD Settings", "Deutsche Post Settings")


def after_install():
	create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)
	_ensure_singletons()


def after_migrate():
	create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)
	_ensure_singletons()


def before_uninstall():
	"""Custom Fields wieder entfernen, damit die Delivery Note sauber bleibt."""
	for doctype, fields in CUSTOM_FIELDS.items():
		for field in fields:
			name = f"{doctype}-{field['fieldname']}"
			if frappe.db.exists("Custom Field", name):
				frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)


def _ensure_singletons():
	for doctype in SINGLETONS:
		if not frappe.db.exists(doctype, doctype):
			doc = frappe.get_doc({"doctype": doctype})
			doc.flags.ignore_permissions = True
			doc.insert(ignore_if_duplicate=True)
