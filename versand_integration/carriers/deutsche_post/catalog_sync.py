"""Spiegelt GET /app/catalog in die lokalen Nachschlage-Doctypes:

- Deutsche Post Seitenformat  <- pageFormats
- Deutsche Post Produkt       <- contractProducts.products (Code+Preis; die
  API liefert dafür keinen Namen, deshalb Vorbelegung aus COMMON_PRODUCTS).
  Liefert ein Konto gar keine contractProducts (z. B. frische/Eval-
  Portokasse ohne hinterlegte Vertragsprodukte - live beobachtet), wird
  stattdessen direkt mit COMMON_PRODUCTS vorbefüllt statt leer zu bleiben.
- Deutsche Post Motiv         <- publicGallery.items[].images[]. ACHTUNG:
  live verifiziert heißt der Schlüssel "publicGallery", nicht "publicCatalog"
  wie in der OpenAPI-Spec dokumentiert (Doku-Fehler bei DHL) - beide Namen
  werden akzeptiert, falls sich das je ändert.

Bewusstes Verhalten beim wiederholten Sync: Felder, die direkt von der API
kommen, werden immer aktualisiert; das einzige nutzergesteuerte Feld
("Deaktiviert", bei Produkt auch "Bezeichnung") wird nur beim ERSTEN Anlegen
gesetzt und danach nicht mehr überschrieben, damit eine Kuratierung durch
den Nutzer erhalten bleibt.
"""

from __future__ import annotations

import frappe

from versand_integration.carriers.deutsche_post import constants as C

# Live beobachtet: der Seitenformat-Katalog ist keine kleine, generische Liste
# (A4 vs. Etikett) wie bei DHL/DPD, sondern hunderte sehr konkrete Label-
# Drucker-Modelle/Rollenformate (Brother DK-xxxx, Dymo, Leitz ICON, Seiko,
# Herma, ...) - "LABELPRINTER"/"LABELPAGE" ist dabei praktisch der Großteil
# des gesamten Katalogs, filtert also kaum etwas heraus. Deshalb: ALLES beim
# ersten Import deaktiviert lassen, der Nutzer aktiviert gezielt das/die
# Format(e) für den Drucker, den er tatsächlich besitzt (Titel durchsuchen,
# z. B. nach "Versand-Etikett" oder dem eigenen Druckermodell).


def sync_page_formats(formats: list[dict]) -> int:
	count = 0
	for pf in formats:
		format_id = pf.get("id")
		if format_id is None:
			continue
		name = str(format_id)
		page_type = pf.get("pageType")
		values = {
			"title": pf.get("name") or name,
			"page_type": page_type,
			"is_address_possible": 1 if pf.get("isAddressPossible") else 0,
			"is_image_possible": 1 if pf.get("isImagePossible") else 0,
			"description": pf.get("description"),
		}
		if frappe.db.exists("Deutsche Post Seitenformat", name):
			frappe.db.set_value("Deutsche Post Seitenformat", name, values)
		else:
			doc = frappe.get_doc(
				{
					"doctype": "Deutsche Post Seitenformat",
					"name": name,
					"disabled": 1,
					**values,
				}
			)
			doc.insert(ignore_permissions=True)
		count += 1
	return count


def sync_products(products: list[dict]) -> int:
	if not products:
		# Nicht jedes Konto liefert contractProducts über den Katalog-Endpunkt
		# (z. B. frische/Eval-Portokassen ohne hinterlegte Vertragsprodukte) -
		# dann mit der offiziellen Preisliste (COMMON_PRODUCTS: Code -> Name +
		# Preis in Cent) vorbefüllen, statt die Tabelle leer zu lassen.
		products = [
			{"productCode": int(code), "price": price} for code, (_name, price) in C.COMMON_PRODUCTS.items()
		]

	count = 0
	for product in products:
		code = product.get("productCode")
		if code is None:
			continue
		name = str(code)
		price = product.get("price")
		if frappe.db.exists("Deutsche Post Produkt", name):
			if price is not None:
				frappe.db.set_value("Deutsche Post Produkt", name, "price_cent", price)
		else:
			seed_name, seed_price = C.COMMON_PRODUCTS.get(name, (f"Produkt {name}", None))
			doc = frappe.get_doc(
				{
					"doctype": "Deutsche Post Produkt",
					"name": name,
					"title": seed_name,
					"price_cent": price if price is not None else seed_price,
					"disabled": 0,
				}
			)
			doc.insert(ignore_permissions=True)
		count += 1
	return count


def sync_motifs(catalog_items: list[dict]) -> int:
	count = 0
	for item in catalog_items:
		category = item.get("categoryDescription") or item.get("category")
		for image in item.get("images") or []:
			image_id = image.get("imageID")
			if image_id is None:
				continue
			name = str(image_id)
			values = {
				"title": image.get("imageDescription") or name,
				"slogan": image.get("imageSlogan"),
				"category": category,
			}
			if frappe.db.exists("Deutsche Post Motiv", name):
				frappe.db.set_value("Deutsche Post Motiv", name, values)
			else:
				doc = frappe.get_doc(
					{"doctype": "Deutsche Post Motiv", "name": name, "disabled": 0, **values}
				)
				doc.insert(ignore_permissions=True)
			count += 1
	return count


def sync_catalog(catalog: dict) -> dict:
	page_formats = catalog.get("pageFormats") or []
	products = ((catalog.get("contractProducts") or {}).get("products")) or []
	# Live-verifiziert (2026-09): der tatsächliche Schlüssel heißt "publicGallery",
	# nicht "publicCatalog" wie in der OpenAPI-Spec dokumentiert (Doku-Fehler bei DHL).
	motifs = (catalog.get("publicGallery") or catalog.get("publicCatalog") or {}).get("items") or []
	return {
		"page_formats": sync_page_formats(page_formats),
		"products": sync_products(products),
		"motifs": sync_motifs(motifs),
	}
