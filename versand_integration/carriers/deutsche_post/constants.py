"""Konstanten für Deutsche Post Internetmarke – OneClickForApp (1C4A) V3, SOAP."""

# Es gibt für 1C4A keine separate Sandbox – Test läuft gegen Produktion mit
# echtem Portokasse-Guthaben (Kleinstbeträge).
ENDPOINT = "https://internetmarke.deutschepost.de:443/OneClickForAppV3/OneClickForAppServiceV3"

NS_V3 = "http://oneclickforapp.dpag.de/V3"
NS_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"

SIGNATURE_ALGORITHM = "sha-512"

# Häufige Produktcodes (Briefe). Verbindlich ist die per retrievePublicGallery /
# ProdWS abgerufene Liste – hier nur als Voreinstellung/Hinweis.
COMMON_PRODUCTS = {
	"1": "Standardbrief",
	"21": "Kompaktbrief",
	"31": "Großbrief",
	"41": "Maxibrief",
	"79": "Postkarte",
}
DEFAULT_PRODUCT_CODE = "1"

# retrievePageFormats liefert IDs; 1 = DIN A4 Standard.
DEFAULT_PAGE_FORMAT_ID = 1

# positions/voucherLayout
VOUCHER_LAYOUTS = ["AddressZone", "FrankingZone"]
DEFAULT_VOUCHER_LAYOUT = "AddressZone"
