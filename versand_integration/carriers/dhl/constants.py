"""Konstanten für die DHL Parcel DE Shipping API v2.

Doku: https://developer.dhl.com/api-reference/parcel-de-shipping-post-parcel-germany-v2
"""

# --- Endpunkte -------------------------------------------------------------
SANDBOX_BASE_URL = "https://api-sandbox.dhl.com/parcel/de/shipping/v2"
PRODUCTION_BASE_URL = "https://api-eu.dhl.com/parcel/de/shipping/v2"

SANDBOX_TOKEN_URL = "https://api-sandbox.dhl.com/parcel/de/account/auth/ropc/v1/token"
PRODUCTION_TOKEN_URL = "https://api-eu.dhl.com/parcel/de/account/auth/ropc/v1/token"

# --- Sandbox-Testzugang (öffentlich dokumentiert) -------------------------
# Klassischer Basic-Auth-Benutzer der Sandbox.
SANDBOX_GKP_USERNAME = "sandy_sandbox"
SANDBOX_GKP_PASSWORD = "pass"
# OAuth2-(ROPC-)Testbenutzer der Sandbox (DHL Onboarding-Collection).
SANDBOX_OAUTH_USERNAME = "user-valid"
SANDBOX_OAUTH_PASSWORD = "SandboxPasswort2023!"

# 14-stellige Abrechnungsnummern der Sandbox (EKP 3333333333 + Verfahren + Teilnahme).
# "...0102" = mit Services, "...0101" = ohne Services.
SANDBOX_BILLING_NUMBERS = {
	"V01PAK": "33333333330102",   # DHL Paket
	"V53WPAK": "33333333335301",  # DHL Paket International
	"V54EPAK": "33333333335401",  # DHL Europaket
	"V62WP": "33333333336201",    # Warenpost (Altname)
	"V62KP": "33333333336201",    # DHL Kleinpaket
	"V66WPI": "33333333336601",   # Warenpost International
}
SANDBOX_RETURN_BILLING_NUMBER = "33333333330701"

DEFAULT_PROFILE = "STANDARD_GRUPPENPROFIL"

# --- Produkte ------------------------------------------------------------
# Anzeigename -> DHL-Code. In den Auswahlfeldern steht der lesbare Name,
# `resolve_product()` übersetzt ihn zurück (Code wird ebenfalls akzeptiert).
PRODUCTS = {
	"V01PAK": "DHL Paket (national)",
	"V53WPAK": "DHL Paket International",
	"V54EPAK": "DHL Europaket",
	"V62KP": "DHL Kleinpaket (national)",
	"V62WP": "Warenpost (Altvertrag)",
	"V66WPI": "Warenpost International",
}
LABELS = list(PRODUCTS.values())
_LABEL_TO_CODE = {label: code for code, label in PRODUCTS.items()}


def resolve_product(value: str | None) -> str | None:
	if not value:
		return None
	value = value.strip()
	if value in PRODUCTS:  # bereits ein Code
		return value
	if value in _LABEL_TO_CODE:  # lesbarer Name
		return _LABEL_TO_CODE[value]
	head = value.split(" ")[0].split("—")[0].strip()  # toleriert "V01PAK – ..."
	if head in PRODUCTS:
		return head
	from versand_integration.carriers.exceptions import CarrierConfigError

	raise CarrierConfigError(f"Unbekanntes DHL-Produkt: {value!r}")


def product_label(code: str | None) -> str:
	return PRODUCTS.get(code or "", code or "")

# --- Druckformate ------------------------------------------------------
# https://developer.dhl.com/ – printFormat. Anzeigename orientiert sich an der
# Bezeichnung im DHL-Geschäftskundenportal ("Druckeinstellungen einrichten"),
# damit man die eigene Portal-Einstellung wiedererkennt; der Code steht in
# Klammern und ist maßgeblich.
PRINT_FORMATS = {
	"910-300-700": "Common Label Laserdruck 105×205 mm – DIN A5 (910-300-700)",
	"910-300-700-oz": "Common Label Laserdruck 105×205 mm – DIN A5, ohne Zusatzetikett (910-300-700-oz)",
	"910-300-300": "Common Label Laserdruck 105×148 mm – DIN A5 (910-300-300)",
	"910-300-300-oz": "Common Label Laserdruck 105×148 mm – DIN A5, ohne Zusatzetikett (910-300-300-oz)",
	"910-300-710": "Common Label Laserdruck 105×208 mm (910-300-710)",
	"910-300-600": "Common Label Thermodruck 103×199 mm (910-300-600)",
	"910-300-610": "Common Label Thermodruck 103×199 mm (910-300-610)",
	"910-300-400": "Common Label Thermodruck 103×150 mm (910-300-400)",
	"910-300-410": "Common Label Thermodruck 103×150 mm (910-300-410)",
	"100x70mm": "Thermodruck 100×70 mm (100x70mm)",
	"A4": "DIN A4 Normalpapier (A4)",
}
PRINT_FORMAT_LABELS = list(PRINT_FORMATS.values())
_PRINT_FORMAT_LABEL_TO_CODE = {label: code for code, label in PRINT_FORMATS.items()}
DEFAULT_PRINT_FORMAT = "910-300-700"


def resolve_print_format(value: str | None) -> str | None:
	"""Lesbarer Name ODER Rohcode -> DHL-Code. Unbekannte Werte kommen unverändert
	durch (z. B. wenn DHL das Portal-Format-Angebot mal erweitert)."""
	if not value:
		return None
	value = value.strip()
	if value in PRINT_FORMATS:
		return value
	if value in _PRINT_FORMAT_LABEL_TO_CODE:
		return _PRINT_FORMAT_LABEL_TO_CODE[value]
	return value

DOC_FORMATS = ["PDF", "ZPL2"]
DEFAULT_DOC_FORMAT = "PDF"

TRACKING_URL_TEMPLATE = (
	"https://www.dhl.de/de/privatkunden/pakete-empfangen/verfolgen.html?piececode={number}"
)

# EU-Mitgliedstaaten (ISO alpha-3) – für die automatische Premium-Regel.
EU_COUNTRIES = {
	"AUT", "BEL", "BGR", "HRV", "CYP", "CZE", "DNK", "EST", "FIN", "FRA",
	"DEU", "GRC", "HUN", "IRL", "ITA", "LVA", "LTU", "LUX", "MLT", "NLD",
	"POL", "PRT", "ROU", "SVK", "SVN", "ESP", "SWE",
}

# --- Länder: ISO 3166-1 alpha-2 -> alpha-3 -------------------------------
# ERPNext speichert im Country-Doctype den alpha-2 Code (`code`). DHL erwartet
# alpha-3. Häufig genutzte Ziele; weitere bei Bedarf ergänzen.
ALPHA2_TO_ALPHA3 = {
	"DE": "DEU", "AT": "AUT", "CH": "CHE", "FR": "FRA", "IT": "ITA", "ES": "ESP",
	"PT": "PRT", "NL": "NLD", "BE": "BEL", "LU": "LUX", "DK": "DNK", "SE": "SWE",
	"NO": "NOR", "FI": "FIN", "IS": "ISL", "IE": "IRL", "GB": "GBR", "PL": "POL",
	"CZ": "CZE", "SK": "SVK", "HU": "HUN", "SI": "SVN", "HR": "HRV", "RO": "ROU",
	"BG": "BGR", "GR": "GRC", "EE": "EST", "LV": "LVA", "LT": "LTU", "MT": "MLT",
	"CY": "CYP", "US": "USA", "CA": "CAN", "AU": "AUS", "NZ": "NZL", "JP": "JPN",
	"CN": "CHN", "HK": "HKG", "SG": "SGP", "AE": "ARE", "TR": "TUR", "LI": "LIE",
	"MC": "MCO", "SM": "SMR", "AD": "AND", "VA": "VAT", "RS": "SRB", "BA": "BIH",
	"ME": "MNE", "MK": "MKD", "AL": "ALB", "UA": "UKR", "MD": "MDA", "BR": "BRA",
	"MX": "MEX", "ZA": "ZAF", "IN": "IND", "IL": "ISR", "KR": "KOR", "TH": "THA",
}
