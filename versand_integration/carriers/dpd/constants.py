"""Konstanten für DPD DE WebConnect (SOAP: LoginService V2.0, ShipmentService V4.5)."""

STAGE_BASE = "https://public-ws-stage.dpd.com/services"
PROD_BASE = "https://public-ws.dpd.com/services"

LOGIN_SERVICE_PATH = "/LoginService/V2_0/"
SHIPMENT_SERVICE_PATH = "/ShipmentService/V4_5/"

MESSAGE_LANGUAGE = "de_DE"
SOFTWARE_VERSION = "ERPNext-Versand-Integration"

# Auth-Token gilt bei DPD ~24 h – etwas kürzer cachen.
TOKEN_TTL_SECONDS = 20 * 60 * 60

# generalShipmentData/product  (DPD-Code -> Anzeigename)
PRODUCTS = {
	"CL": "DPD Classic (national/EU)",
	"CL2SHOP": "DPD Classic an Pickup-Paketshop",
	"SHOP2SHOP": "DPD Shop2Shop",
	"E12": "DPD Express 12:00",
	"E18": "DPD Express 18:00",
	"E830": "DPD Express 8:30",
	"IE2": "DPD International Express",
	"PSD": "DPD Parcelshop-Zustellung (Predict)",
	"MAIL": "DPD Priority (Mail)",
}
LABELS = list(PRODUCTS.values())
_LABEL_TO_CODE = {label: code for code, label in PRODUCTS.items()}
DEFAULT_PRODUCT = "CL"


def resolve_product(value: str | None) -> str:
	if not value:
		return DEFAULT_PRODUCT
	value = value.strip()
	if value in PRODUCTS:
		return value
	if value in _LABEL_TO_CODE:
		return _LABEL_TO_CODE[value]
	head = value.split(" ")[0].strip()
	return head if head in PRODUCTS else value  # unbekannt -> unverändert an DPD


def product_label(code: str | None) -> str:
	return PRODUCTS.get(code or "", code or "")

# printOptions/printOption/paperFormat
PAPER_FORMATS = ["A4", "A5", "A6", "A7"]
DEFAULT_PAPER_FORMAT = "A6"

# printOptions/printOption/outputFormat
OUTPUT_FORMATS = ["PDF", "ZPL", "ZPL300", "PKPASS"]
DEFAULT_OUTPUT_FORMAT = "PDF"

# productAndServiceData/orderType
ORDER_TYPE = "consignment"

TRACKING_URL_TEMPLATE = "https://tracking.dpd.de/status/de_DE/parcel/{number}"


def base_url(environment: str) -> str:
	return STAGE_BASE if (environment or "Sandbox") in ("Sandbox", "Stage") else PROD_BASE
