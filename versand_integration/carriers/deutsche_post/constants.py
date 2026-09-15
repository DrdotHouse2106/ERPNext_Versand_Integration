"""Konstanten für die neue REST-API "Post DE Internetmarke" (DHL Developer Portal).

Löst die alte SOAP-Anbindung (OneClickForApp / 1C4A V3, Partnervertrag) ab: seit
kurzem läuft die Internetmarke über dasselbe Developer-Portal-App-Modell wie
"Parcel DE Shipping"/"Parcel DE Tracking" – kein separater Partnervertrag mehr
nötig, nur die API im Developer Portal für die eigene App freischalten lassen.

Basis-URL, Auth-Flow und die Warenkorb-/Checkout-Endpunkte sind seit der vom
User bereitgestellten offiziellen OpenAPI-Spec ("Deutsche Post INTERNETMARKE
API", Division Post & Parcel Germany, Version 1.30) vollständig verifiziert –
keine Vermutungen mehr. Auth (POST {base}/user, application/x-www-form-
urlencoded): grant_type=client_credentials, client_id, client_secret
(Developer-Portal-App, i. d. R. dieselben Werte wie DHL Settings.api_key/
api_secret), username + password (Portokasse-Login) -> Bearer-Token. Live
bestätigt (Token-Austausch erfolgreich).
"""

DEFAULT_BASE_URL = "https://api-eu.dhl.com/post/de/shipping/im/v1"

# ApiVersionResource - Healthcheck, keine Auth noetig.
HEALTH_PATH = "/"

# UserResource
TOKEN_PATH = "/user"  # POST, Bearer-Token holen
USER_PROFILE_PATH = "/user/profile"  # GET, Profildaten des autorisierten Users

# AppResource - Warenkorb/Checkout/Retoure/Katalog.
WALLET_PATH = "/app/wallet"  # PUT, Guthaben aufladen (?amount=<eurocent>)
SHOPPING_CART_PATH = "/app/shoppingcart"  # POST, initialisiert Warenkorb -> shopOrderId
SHOPPING_CART_PATH_TMPL = "/app/shoppingcart/{shop_order_id}"  # GET, Warenkorb abrufen
SHOPPING_CART_PNG_PATH = "/app/shoppingcart/png"  # POST, PNG-Checkout/Vorschau
SHOPPING_CART_PDF_PATH = "/app/shoppingcart/pdf"  # POST, PDF-Checkout/Vorschau
RETOURE_PATH = "/app/retoure"  # GET (Status) / POST (beantragen)
CATALOG_PATH = "/app/catalog"  # GET, Motiv-/Bildkataloge (?types=PUBLIC&types=PAGE_FORMATS)

CATALOG_TYPE_PUBLIC = "PUBLIC"
CATALOG_TYPE_PAGE_FORMATS = "PAGE_FORMATS"

# Häufige Produktcodes (Briefe). Verbindlich ist die von der API selbst
# gelieferte Produktliste (GET /app/catalog) – hier nur als Voreinstellung/Hinweis.
COMMON_PRODUCTS = {
	"1": "Standardbrief",
	"21": "Kompaktbrief",
	"31": "Großbrief",
	"41": "Maxibrief",
	"79": "Postkarte",
}
DEFAULT_PRODUCT_CODE = "1"

DEFAULT_PAGE_FORMAT_ID = 1

# Select-Optionen in den Settings (lesbar) <-> API-Enum (voucherLayout).
VOUCHER_LAYOUTS = ["AddressZone", "FrankingZone"]
DEFAULT_VOUCHER_LAYOUT = "AddressZone"
VOUCHER_LAYOUT_API = {
	"AddressZone": "ADDRESS_ZONE",
	"FrankingZone": "FRANKING_ZONE",
}

# Vorschau-Modus: kostenlos, KEIN Portokasse-Abzug, Muster-PDF ohne gültige
# Frankierung (AppShoppingCartPreviewPDFRequest, kein "total"/keine Adressen
# nötig). Produktiv = echter Kauf (AppShoppingCartPDFRequest).
MODE_PREVIEW = "Vorschau (kostenlos)"
MODE_PRODUCTIVE = "Produktiv (Portokasse wird belastet)"

PREVIEW_DEFAULT_IMAGE_ID = "2145969140"

# VoucherPosition ist fuer PDF-Marken Pflicht ("Values >0 are mandatory"),
# aber nur die Position im Ausdruck (nicht die Frankierung) - Standardwert
# fuer "eine Marke, eine Seite" reicht.
DEFAULT_VOUCHER_POSITION = {"labelX": 1, "labelY": 1, "page": 1}
