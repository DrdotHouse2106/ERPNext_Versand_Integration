app_name = "versand_integration"
app_title = "Versand Integration"
app_publisher = "Marcel Ulber"
app_description = "Versandetiketten direkt über Carrier-APIs (DHL Parcel DE Shipping v2)."
app_email = "drdothouse@gmail.com"
app_license = "MIT"

# Wir verlinken auf Delivery Note / Address / Customer aus ERPNext.
required_apps = ["frappe/erpnext"]

# ---------------------------------------------------------------------------
# Client-Skripte
# ---------------------------------------------------------------------------
doctype_js = {
	"Delivery Note": "public/js/delivery_note.js",
}

# ---------------------------------------------------------------------------
# Installation / Migration
# ---------------------------------------------------------------------------
after_install = "versand_integration.setup.install.after_install"
after_migrate = "versand_integration.setup.install.after_migrate"
before_uninstall = "versand_integration.setup.install.before_uninstall"

# ---------------------------------------------------------------------------
# Fixtures (die Custom Fields werden zusätzlich in after_install angelegt,
# die Fixtures sorgen für saubere Versionierung / Export).
# ---------------------------------------------------------------------------
fixtures = [
	{
		"dt": "Custom Field",
		"filters": [["name", "in", [
			"Delivery Note-vi_versand_section",
			"Delivery Note-vi_versandsendung",
			"Delivery Note-vi_column_break_versand",
			"Delivery Note-vi_sendungsnummer",
			"Delivery Note-vi_tracking_url",
		]]],
	},
]
