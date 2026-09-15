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

# Vorrangig ist die Produktliste, die die API pro Konto selbst liefert
# (GET /app/catalog -> contractProducts, siehe catalog_sync.py + Doctype
# "Deutsche Post Produkt"). Liefert das Konto dort nichts (z. B. frische/
# Eval-Portokasse ohne hinterlegte Vertragsprodukte - live beobachtet), wird
# stattdessen dieses Wörterbuch als Fallback genutzt: {Code: (Name, Preis in
# Cent)}, abgetippt aus der offiziellen Preisliste "PPL60_EPORTO" (Deutsche
# Post, Stand 2026-05-13, vom User bereitgestellt) - keine Vermutung, echte
# Vertragsdaten. Zwei Kilotarif-International-Produkte (10162/10166), die
# laut Preisliste einen gesonderten Vertrag brauchen, sind bewusst
# ausgelassen. Namen/Preise dürfen im Doctype frei angepasst werden, falls
# sich die offizielle Liste ändert.
COMMON_PRODUCTS = {
	"1": ("Standardbrief", 95),
	"11": ("Kompaktbrief", 110),
	"21": ("Großbrief", 180),
	"31": ("Maxibrief", 290),
	"41": ("Maxibrief bis 2000 g + Zusatzentgelt MBf", 510),
	"51": ("Postkarte", 95),
	"290": ("Warensendung", 270),
	"331": ("Warensendung 2.000 + Gewichtszuschlag", 355),
	"401": ("Streifbandzeitung bis 50 g", 107),
	"407": ("Streifbandzeitung 51 g bis 500 g", 173),
	"405": ("Streifbandzeitung 501 g bis 1000 g", 286),
	"347": ("Dialogpost Karte Internetmarke", 36),
	"348": ("Dialogpost Standard Internetmarke bis 20g", 38),
	"349": ("Dialogpost Standard Internetmarke 21 - 50g", 42),
	"350": ("Dialogpost Groß Internetmarke bis 50g", 54),
	"351": ("Dialogpost Groß Internetmarke 51 - 100g", 67),
	"352": ("Dialogpost Groß Internetmarke 101 - 250g", 82),
	"353": ("Dialogpost Groß Internetmarke 251 - 500g", 94),
	"354": ("Dialogpost Groß Internetmarke 501 - 1000g", 111),
	"1002": ("Standardbrief Integral + EINSCHREIBEN EINWURF", 330),
	"1007": ("Standardbrief Integral + EINSCHREIBEN", 360),
	"1008": ("Standardbrief Integral + EINSCHREIBEN + RÜCKSCHEIN", 580),
	"1012": ("Kompaktbrief Integral + EINSCHREIBEN EINWURF", 345),
	"1017": ("Kompaktbrief Integral + EINSCHREIBEN", 375),
	"1018": ("Kompaktbrief Integral + EINSCHREIBEN + RÜCKSCHEIN", 595),
	"1022": ("Großbrief Integral + EINSCHREIBEN EINWURF", 415),
	"1027": ("Großbrief Integral + EINSCHREIBEN", 445),
	"1028": ("Großbrief Integral + EINSCHREIBEN + RÜCKSCHEIN", 665),
	"1032": ("Maxibrief Integral + EINSCHREIBEN EINWURF", 525),
	"1037": ("Maxibrief Integral + EINSCHREIBEN", 555),
	"1038": ("Maxibrief Integral + EINSCHREIBEN + RÜCKSCHEIN", 775),
	"1042": ("Maxibrief Integral + Zusatzentgelt MBf + EINSCHREIBEN EINWURF", 745),
	"1047": ("Maxibrief Integral + Zusatzentgelt MBf + EINSCHREIBEN", 775),
	"1048": ("Maxibrief Integral + Zusatzentgelt MBf + EINSCHREIBEN + RÜCKSCHEIN", 995),
	"1052": ("Postkarte Integral + EINSCHREIBEN EINWURF", 330),
	"1057": ("Postkarte Integral + EINSCHREIBEN", 360),
	"1058": ("Postkarte Integral + EINSCHREIBEN + RÜCKSCHEIN", 580),
	"10001": ("Standardbrief Intern. GK", 125),
	"10011": ("Kompaktbrief Intern. GK", 180),
	"10051": ("Großbrief Intern. GK", 330),
	"10071": ("Maxibrief Intern. bis 1.000g GK", 650),
	"10091": ("Maxibrief Intern. bis 2.000g GK", 1700),
	"10201": ("Postkarte Intern. GK", 125),
	"11006": ("Standardbrief Intern. GK Integral + EINSCHREIBEN", 495),
	"11016": ("Kompaktbrief Intern. GK Integral + EINSCHREIBEN", 550),
	"11056": ("Großbrief Intern. GK Integral + EINSCHREIBEN", 700),
	"11076": ("Maxibrief Intern. bis 1.000g GK Integral + EINSCHREIBEN", 1020),
	"11096": ("Maxibrief Intern. bis 2.000g GK Integral + EINSCHREIBEN", 2070),
	"11202": ("Postkarte Intern. GK Integral + EINSCHREIBEN", 495),
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
