"""Konstanten für die neue REST-API "Post DE Internetmarke" (DHL Developer Portal).

Löst die alte SOAP-Anbindung (OneClickForApp / 1C4A V3, Partnervertrag) ab: seit
kurzem läuft die Internetmarke über dasselbe Developer-Portal-App-Modell wie
"Parcel DE Shipping"/"Parcel DE Tracking" – kein separater Partnervertrag mehr
nötig, nur die API im Developer Portal für die eigene App freischalten lassen.

Auth (bestätigt von DHL-Support, s. README):
  1) App-Ebene: `dhl-client-id`-Header = Client ID/Consumer Key der eigenen
     Developer-Portal-App (meist dieselbe App wie DHL Settings.api_key).
  2) User-Ebene: POST {base}/user mit {"username": <Portokasse-E-Mail>,
     "password": <Portokasse-Passwort>} -> Bearer-Token.
  3) Weitere Aufrufe mit `Authorization: Bearer <token>`.

WICHTIG: Die genaue Basis-URL sowie die Endpunkte/Bodies für Marken-Erstellung
und Warenkorb sind (Stand jetzt) NICHT anhand einer offiziellen Spezifikation
verifiziert – nur der Token-Austausch ist von DHL bestätigt. Bitte die
Basis-URL in den Deutsche Post Settings prüfen/anpassen, sobald die
API-Referenz im Developer Portal vorliegt (API-Status dort aktuell "Pending").
"""

# Bestbekannte Vermutung nach dem Namensschema der anderen "Post & Parcel
# Germany"-APIs (parcel/de/shipping/v2, parcel/de/tracking/v0, …) – NICHT
# verifiziert. In den Settings überschreibbar.
DEFAULT_BASE_URL = "https://api-eu.dhl.com/post/de/shipping/im/v1"

TOKEN_PATH = "/user"  # von DHL bestätigt

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
