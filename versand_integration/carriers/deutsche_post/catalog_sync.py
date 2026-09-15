"""Spiegelt GET /app/catalog in die lokalen Nachschlage-Doctypes:

- Deutsche Post Seitenformat  <- pageFormats
- Deutsche Post Produkt       <- contractProducts.products (Code+Preis; die
  API liefert dafür keinen Namen, deshalb Vorbelegung aus COMMON_PRODUCTS)
- Deutsche Post Motiv         <- publicCatalog.items[].images[]

Bewusstes Verhalten beim wiederholten Sync: Felder, die direkt von der API
kommen, werden immer aktualisiert; das einzige nutzergesteuerte Feld
("Deaktiviert", bei Produkt auch "Bezeichnung") wird nur beim ERSTEN Anlegen
gesetzt und danach nicht mehr überschrieben, damit eine Kuratierung durch
den Nutzer erhalten bleibt.
"""

from __future__ import annotations

import frappe

from versand_integration.carriers.deutsche_post import constants as C

# A4-Papier/Umschlag ist für unseren Versandlabel-Anwendungsfall meist Rauschen -
# beim ersten Import deaktiviert, Etikettenformate bleiben aktiv.
_NOISY_PAGE_TYPES = {"REGULARPAGE", "ENVELOPE"}


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
					"disabled": 1 if page_type in _NOISY_PAGE_TYPES else 0,
					**values,
				}
			)
			doc.insert(ignore_permissions=True)
		count += 1
	return count


def sync_products(products: list[dict]) -> int:
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
			doc = frappe.get_doc(
				{
					"doctype": "Deutsche Post Produkt",
					"name": name,
					"title": C.COMMON_PRODUCTS.get(name, f"Produkt {name}"),
					"price_cent": price,
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
	motifs = ((catalog.get("publicCatalog") or {}).get("items")) or []
	return {
		"page_formats": sync_page_formats(page_formats),
		"products": sync_products(products),
		"motifs": sync_motifs(motifs),
	}
