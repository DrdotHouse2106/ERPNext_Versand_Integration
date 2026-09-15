"""Konstanten für die neue REST-API "Post DE Internetmarke" (DHL Developer Portal).

Löst die alte SOAP-Anbindung (OneClickForApp / 1C4A V3, Partnervertrag) ab: seit
kurzem läuft die Internetmarke über dasselbe Developer-Portal-App-Modell wie
"Parcel DE Shipping"/"Parcel DE Tracking" – kein separater Partnervertrag mehr
nötig, nur die API im Developer Portal für die eigene App freischalten lassen.

Auth (offizielle API-Referenz, POST {base}/user, application/x-www-form-urlencoded):
  grant_type=client_credentials, client_id, client_secret (Developer-Portal-
  App, meist dieselben Werte wie DHL Settings.api_key/api_secret), username +
  password (Portokasse-Login) -> Bearer-Token. Weitere Aufrufe mit
  `Authorization: Bearer <token>`. Live bestätigt (Token-Austausch erfolgreich).

Basis-URL und Auth sind seit der offiziellen API-Referenz ("Post DE
Internetmarke", Division Post & Parcel Germany) verifiziert. Die übrigen
Endpunkte unten (AppResource: Warenkorb/Checkout/Retoure/Katalog) sind aus der
Referenz-Übersicht bekannt, aber ihre Request-/Response-Bodies noch nicht -
dafür fehlt weiterhin das Detail-Schema (z. B. aus der herunterladbaren
OpenAPI-Spec). Marken-Erstellung bleibt deshalb vorerst nicht implementiert.
"""

# Von DHL offiziell bestätigt (API-Referenz "Post DE Internetmarke").
DEFAULT_BASE_URL = "https://api-eu.dhl.com/post/de/shipping/im/v1"

# ApiVersionResource - Healthcheck, keine Auth noetig.
HEALTH_PATH = "/"

# UserResource
TOKEN_PATH = "/user"  # POST, Bearer-Token holen
USER_PROFILE_PATH = "/user/profile"  # GET, Profildaten des autorisierten Users

# AppResource - Warenkorb/Checkout/Retoure/Katalog. Pfade aus der Referenz-
# Uebersicht bekannt, Bodies noch nicht verifiziert (siehe Docstring oben).
WALLET_PATH = "/app/wallet"  # PUT, Guthaben aufladen
SHOPPING_CART_PATH = "/app/shoppingcart"  # POST, initialisiert Warenkorb -> shopOrderId
SHOPPING_CART_PATH_TMPL = "/app/shoppingcart/{shop_order_id}"  # GET, Warenkorb abrufen
SHOPPING_CART_PNG_PATH = "/app/shoppingcart/png"  # POST, PNG-Checkout/Vorschau
SHOPPING_CART_PDF_PATH = "/app/shoppingcart/pdf"  # POST, PDF-Checkout/Vorschau
RETOURE_PATH = "/app/retoure"  # GET (Status) / POST (beantragen)
CATALOG_PATH = "/app/catalog"  # GET, Motiv-/Bildkataloge

# Häufige Produktcodes (Briefe). Verbindlich ist die von der API selbst
# gelieferte Produktliste – hier nur als Voreinstellung/Hinweis.
COMMON_PRODUCTS = {
	"1": "Standardbrief",
	"21": "Kompaktbrief",
	"31": "Großbrief",
	"41": "Maxibrief",
	"79": "Postkarte",
}
DEFAULT_PRODUCT_CODE = "1"

DEFAULT_PAGE_FORMAT_ID = 1

VOUCHER_LAYOUTS = ["AddressZone", "FrankingZone"]
DEFAULT_VOUCHER_LAYOUT = "AddressZone"

# Vorschau-Modus: kostenlos, KEIN Portokasse-Abzug, Muster-PDF ohne gültige
# Frankierung. Konkreter Endpunkt in der neuen REST-API noch offen.
MODE_PREVIEW = "Vorschau (kostenlos)"
MODE_PRODUCTIVE = "Produktiv (Portokasse wird belastet)"

PREVIEW_DEFAULT_IMAGE_ID = "2145969140"
