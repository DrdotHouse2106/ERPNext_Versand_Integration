"""Konstanten für die DHL Parcel DE Shipping API v2.

Doku: https://developer.dhl.com/api-reference/parcel-de-shipping-post-parcel-germany-v2
"""

# --- Endpunkte -------------------------------------------------------------
SANDBOX_BASE_URL = "https://api-sandbox.dhl.com/parcel/de/shipping/v2"
PRODUCTION_BASE_URL = "https://api-eu.dhl.com/parcel/de/shipping/v2"

SANDBOX_TOKEN_URL = "https://api-sandbox.dhl.com/parcel/de/account/auth/ropc/v1/token"
PRODUCTION_TOKEN_URL = "https://api-eu.dhl.com/parcel/de/account/auth/ropc/v1/token"

# --- Sandbox-Testzugang (öffentlich dokumentiert) -------------------------
# Basic-Auth-Benutzer des DHL-Geschäftskundenportals in der Sandbox.
SANDBOX_GKP_USERNAME = "sandy_sandbox"
SANDBOX_GKP_PASSWORD = "pass"
# 14-stellige Abrechnungsnummern (EKP 3333333333 + Verfahren + Teilnahme)
SANDBOX_BILLING_NUMBERS = {
	"V01PAK": "33333333330101",   # DHL Paket
	"V53WPAK": "33333333335301",  # DHL Paket International
	"V54EPAK": "33333333335401",  # DHL Europaket
	"V62WP": "33333333330102",    # Warenpost
	"V66WPI": "33333333336601",   # Warenpost International
}
SANDBOX_RETURN_BILLING_NUMBER = "33333333330701"

DEFAULT_PROFILE = "STANDARD_GRUPPENPROFIL"

# --- Produkte ------------------------------------------------------------
PRODUCTS = {
	"V01PAK": "DHL Paket (national)",
	"V53WPAK": "DHL Paket International",
	"V54EPAK": "DHL Europaket",
	"V62WP": "Warenpost",
	"V66WPI": "Warenpost International",
}

# --- Druckformate ------------------------------------------------------
# https://developer.dhl.com/ – printFormat
PRINT_FORMATS = [
	"910-300-700",       # A4 Common-Label
	"910-300-700-oz",    # A4 ohne Zusatzetikett
	"910-300-600",       # 103 x 199 mm (Laserdrucker)
	"910-300-610",       # 103 x 199 mm ohne Zusatzetikett
	"910-300-710",       # 103 x 150 mm (Thermodrucker)
	"100x70mm",
	"A4",
]
DEFAULT_PRINT_FORMAT = "910-300-700"

DOC_FORMATS = ["PDF", "ZPL2"]
DEFAULT_DOC_FORMAT = "PDF"

TRACKING_URL_TEMPLATE = (
	"https://www.dhl.de/de/privatkunden/pakete-empfangen/verfolgen.html?piececode={number}"
)

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
