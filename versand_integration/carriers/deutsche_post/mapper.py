"""Versandsendung -> 1C4A `positions`-XML (eine Briefmarke pro Sendung)."""

from __future__ import annotations

from html import escape

from frappe import _
from frappe.utils import cint

from versand_integration.carriers.deutsche_post import constants as C
from versand_integration.carriers.exceptions import CarrierConfigError


def _name_block(name1, name2):
	name1 = (name1 or "").strip()
	if not name1:
		raise CarrierConfigError(_("Deutsche Post: Empfänger-/Absendername fehlt."))
	parts = name1.split(" ", 1)
	if name2 or len(parts) == 1:
		# Als Firma behandeln
		company = escape(name1)
		extra = f"<v3:company>{escape(name2)}</v3:company>" if name2 else ""
		return f"<v3:name><v3:companyName><v3:company>{company}</v3:company>{extra}</v3:companyName></v3:name>"
	first, last = parts[0], parts[1]
	return (
		"<v3:name><v3:personName>"
		f"<v3:firstname>{escape(first)}</v3:firstname>"
		f"<v3:lastname>{escape(last)}</v3:lastname>"
		"</v3:personName></v3:name>"
	)


def _addr_block(street, house_no, zip_code, city, country, additional=None):
	extra = f"<v3:additional>{escape(additional)}</v3:additional>" if additional else ""
	return (
		"<v3:address>"
		f"{extra}"
		f"<v3:street>{escape((street or '').strip())}</v3:street>"
		f"<v3:houseNo>{escape(str(house_no or '').strip())}</v3:houseNo>"
		f"<v3:zip>{escape((zip_code or '').replace(' ', ''))}</v3:zip>"
		f"<v3:city>{escape((city or '').strip())}</v3:city>"
		f"<v3:country>{escape(country or 'Deutschland')}</v3:country>"
		"</v3:address>"
	)


def _party(name1, name2, street, house_no, zip_code, city, country, additional=None):
	return _name_block(name1, name2) + _addr_block(street, house_no, zip_code, city, country, additional)


def build_positions_xml(settings, doc) -> tuple[str, int]:
	"""Gibt (positions_xml, total_cent) zurück."""
	product_code = (doc.product_override or settings.default_product_code or C.DEFAULT_PRODUCT_CODE).strip()
	layout = settings.voucher_layout or C.DEFAULT_VOUCHER_LAYOUT

	amount = cint(doc.dp_franking_cent) or cint(settings.default_franking_cent)
	if not amount:
		raise CarrierConfigError(
			_("Deutsche Post: Frankierbetrag (Cent) fehlt – an der Sendung oder in den Settings hinterlegen.")
		)

	sender = _party(
		settings.sender_name1,
		settings.sender_name2,
		settings.sender_street,
		settings.sender_house_number,
		settings.sender_zip,
		settings.sender_city,
		settings.sender_country or "Deutschland",
	)
	receiver = _party(
		doc.receiver_name,
		doc.receiver_name2,
		doc.receiver_street,
		doc.receiver_house_number,
		doc.receiver_postal_code,
		doc.receiver_city,
		_country_name(doc.receiver_country),
		additional=doc.receiver_address_addition,
	)

	address_xml = ""
	if layout == "AddressZone":
		address_xml = (
			"<v3:address>"
			f"<v3:sender>{sender}</v3:sender>"
			f"<v3:receiver>{receiver}</v3:receiver>"
			"</v3:address>"
		)

	image_xml = f"<v3:imageID>{escape(str(settings.image_id))}</v3:imageID>" if settings.image_id else ""

	positions_xml = (
		"<v3:positions>"
		f"<v3:productCode>{escape(product_code)}</v3:productCode>"
		f"{image_xml}"
		f"{address_xml}"
		f"<v3:voucherLayout>{escape(layout)}</v3:voucherLayout>"
		"</v3:positions>"
	)
	return positions_xml, amount


def _country_name(value) -> str:
	if not value:
		return "Deutschland"
	value = value.strip()
	if value.upper() in ("DE", "DEU", "GERMANY"):
		return "Deutschland"
	return value
