from __future__ import annotations

import base64
import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, get_url_to_form, now_datetime

from versand_integration.carriers import base as cbase
from versand_integration.carriers.base import LabelResult, TrackingNotSupported, TrackingResult
from versand_integration.carriers.exceptions import CarrierError
from versand_integration.carriers.registry import get_carrier

STATUS_DRAFT = "Entwurf"
STATUS_CREATED = "Etikett erstellt"
STATUS_CANCELLED = "Storniert"
STATUS_ERROR = "Fehler"


class Versandsendung(Document):
	# ------------------------------------------------------------- lifecycle
	def validate(self):
		self._sync_from_delivery_note()
		self._split_street()
		self._ensure_weight()
		if not self.status:
			self.status = STATUS_DRAFT

	def before_submit(self):
		if self.status != STATUS_CREATED or not self.shipment_number:
			frappe.throw(
				_("Bitte zuerst über »Etikett erstellen« ein Versandetikett erzeugen.")
			)

	def on_submit(self):
		self._write_back_to_delivery_note()

	def on_cancel(self):
		self.flags.ignore_links = True
		if self.shipment_number and self.status == STATUS_CREATED:
			try:
				self._cancel_with_carrier()
			except CarrierError as exc:
				frappe.throw(
					_("Sendung konnte beim Carrier nicht storniert werden: {0}").format(exc)
				)
		self.status = STATUS_CANCELLED
		self._clear_delivery_note_backref()

	# ------------------------------------------------------------- prefill
	def _sync_from_delivery_note(self):
		if not self.delivery_note:
			return
		dn = frappe.get_doc("Delivery Note", self.delivery_note)
		self.customer = dn.customer
		self.customer_name = dn.customer_name
		if not self.versandabsender:
			self.versandabsender = dn.get("vi_versandabsender")
		if not self.currency:
			self.currency = dn.currency or "EUR"
		if not self.reference:
			self.reference = dn.po_no or dn.name

		if not self.receiver_name:
			self.receiver_name = dn.customer_name

		address_name = dn.shipping_address_name or dn.customer_address
		if address_name and not (self.receiver_street or self.receiver_postal_code):
			addr = frappe.get_doc("Address", address_name)
			self.receiver_name = addr.address_title or self.receiver_name
			self.receiver_street = self.receiver_street or addr.address_line1
			self.receiver_address_addition = self.receiver_address_addition or addr.address_line2
			self.receiver_postal_code = self.receiver_postal_code or addr.pincode
			self.receiver_city = self.receiver_city or addr.city
			self.receiver_country = self.receiver_country or addr.country
			self.receiver_email = self.receiver_email or addr.email_id
			self.receiver_phone = self.receiver_phone or addr.phone

		if not self.receiver_email and dn.contact_email:
			self.receiver_email = dn.contact_email
		if not self.total_weight and not self.packages:
			self.total_weight = flt(dn.total_net_weight)

	def _split_street(self):
		from versand_integration.carriers.dhl.mapper import split_street

		if self.receiver_street and not self.receiver_house_number:
			street, house = split_street(self.receiver_street)
			if house:
				self.receiver_street = street
				self.receiver_house_number = house

	def _ensure_weight(self):
		if self.carrier == "Deutsche Post":
			return  # Briefe: Gewicht steckt im Produktcode, nicht in der Sendung
		if self.packages:
			total = sum(flt(p.weight_kg) for p in self.packages)
			if total <= 0:
				frappe.throw(_("Jedes Paket benötigt ein Gewicht > 0."))
			self.total_weight = total
		elif flt(self.total_weight) <= 0:
			frappe.throw(
				_("Gesamtgewicht (kg) fehlt. Bitte im Lieferschein pflegen oder hier eintragen.")
			)

	# --------------------------------------------------------------- labels
	@frappe.whitelist()
	def create_label(self):
		if self.docstatus != 0:
			frappe.throw(_("Etiketten können nur im Entwurf erstellt werden."))
		if self.status == STATUS_CREATED and self.shipment_number:
			frappe.throw(_("Für diese Sendung existiert bereits ein Etikett ({0}).").format(
				self.shipment_number
			))

		carrier = get_carrier(self.carrier)
		try:
			result: LabelResult = carrier.create_label(self)
		except CarrierError as exc:
			self.status = STATUS_ERROR
			self.error_message = _format_error(exc)
			if getattr(exc, "raw", None):
				self.api_response = json.dumps(exc.raw, indent=2, ensure_ascii=False, default=str)[:100000]
			self.save(ignore_permissions=True)
			frappe.db.commit()
			frappe.throw(self.error_message, title=_("Etikett fehlgeschlagen"))

		self._apply_label_result(result)
		self.save()

		if self._auto_submit_enabled():
			self.submit()
		return {
			"name": self.name,
			"status": self.status,
			"shipment_number": self.shipment_number,
			"tracking_url": self.tracking_url,
			"label_file": self.label_file,
		}

	_SETTINGS_DOCTYPE = {
		"DHL": "DHL Settings",
		"DPD": "DPD Settings",
		"Deutsche Post": "Deutsche Post Settings",
	}

	def _carrier_settings(self):
		return frappe.get_cached_doc(self._SETTINGS_DOCTYPE.get(self.carrier, "DHL Settings"))

	def _auto_submit_enabled(self) -> bool:
		settings = self._carrier_settings()
		if cint(getattr(settings, "validate_only", 0)):
			return False
		# Internetmarke-Vorschau ist keine echte Sendung -> nicht automatisch buchen.
		if self.carrier == "Deutsche Post" and (
			getattr(settings, "mode", "") or ""
		).startswith("Vorschau"):
			return False
		return bool(cint(getattr(settings, "auto_submit", 1)))

	def _apply_label_result(self, result: LabelResult):
		self.status = STATUS_CREATED
		self.error_message = None
		self.shipment_number = result.shipment_number
		self.tracking_number = result.tracking_number
		self.tracking_url = result.tracking_url
		self.api_request = json.dumps(result.raw_request, indent=2, ensure_ascii=False, default=str)
		self.api_response = json.dumps(result.raw_response, indent=2, ensure_ascii=False, default=str)

		if result.label_b64:
			self.label_file = self._save_label(
				result.label_b64, result.label_mimetype, suffix=result.shipment_number
			)

		for pkg, res_pkg in zip(self.packages or [], result.packages, strict=False):
			pkg.shipment_number = res_pkg.shipment_number
			pkg.tracking_number = res_pkg.tracking_number
			if res_pkg.label_b64:
				pkg.label_file = self._save_label(
					res_pkg.label_b64, res_pkg.label_mimetype, suffix=res_pkg.shipment_number
				)

	def _save_label(self, b64: str, mimetype: str, suffix: str) -> str:
		ext = "pdf" if mimetype == "application/pdf" else "zpl"
		filename = f"{self.carrier}-Label-{suffix or self.name}.{ext}"
		_file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": filename,
				"attached_to_doctype": self.doctype,
				"attached_to_name": self.name,
				"is_private": 1,
				"content": base64.b64decode(b64),
			}
		)
		_file.flags.ignore_permissions = True
		_file.insert()
		return _file.file_url

	def _cancel_with_carrier(self):
		carrier = get_carrier(self.carrier)
		result = carrier.cancel_label(self)
		self.api_response = json.dumps(result, indent=2, ensure_ascii=False, default=str)

	# ---------------------------------------------------------- tracking
	@frappe.whitelist()
	def refresh_tracking(self, commit: bool = False):
		if not (self.shipment_number or self.tracking_number):
			frappe.throw(_("Für diese Sendung gibt es noch keine Sendungsnummer."))
		try:
			result: TrackingResult = get_carrier(self.carrier).track(self)
		except TrackingNotSupported:
			frappe.msgprint(_("Für {0} gibt es keine Sendungsverfolgung.").format(self.carrier))
			return {"status": self.tracking_status}
		except CarrierError as exc:
			frappe.throw(_("Tracking fehlgeschlagen: {0}").format(exc))

		changed = self._apply_tracking_result(result)
		self.flags.ignore_validate = True
		self.save(ignore_permissions=True)
		self._mirror_tracking_to_delivery_note()
		if changed and result.status in (cbase.TRACK_PROBLEM, cbase.TRACK_RETURN):
			_notify_problem(self)
		if commit:
			frappe.db.commit()
		return {"status": self.tracking_status, "text": self.tracking_status_text}

	def _apply_tracking_result(self, result: TrackingResult) -> bool:
		previous = self.tracking_status
		self.tracking_status = result.status or cbase.TRACK_UNKNOWN
		self.tracking_status_text = (result.status_text or "")[:280]
		self.tracking_last_update = result.last_update or now_datetime()
		if result.delivered_on:
			self.tracking_delivered_on = result.delivered_on

		self.set("tracking_events", [])
		for ev in result.events:
			self.append(
				"tracking_events",
				{
					"event_time": ev.event_time,
					"status": ev.status,
					"location": ev.location,
					"description": ev.description,
				},
			)

		if self.tracking_status in cbase.TRACK_FINAL:
			self.tracking_polling_active = 0
		return self.tracking_status != previous

	def _mirror_tracking_to_delivery_note(self):
		if not self.delivery_note:
			return
		if frappe.db.get_value("Delivery Note", self.delivery_note, "vi_versandsendung") != self.name:
			return
		frappe.db.set_value(
			"Delivery Note",
			self.delivery_note,
			{
				"vi_tracking_status": self.tracking_status,
				"vi_tracking_delivered_on": self.tracking_delivered_on,
			},
			update_modified=False,
		)

	# ------------------------------------------------- delivery note backref
	def _write_back_to_delivery_note(self):
		if not self.delivery_note:
			return
		frappe.db.set_value(
			"Delivery Note",
			self.delivery_note,
			{
				"vi_versandsendung": self.name,
				"vi_sendungsnummer": self.shipment_number,
				"vi_tracking_url": self.tracking_url,
			},
			update_modified=False,
		)

	def _clear_delivery_note_backref(self):
		if not self.delivery_note:
			return
		if frappe.db.get_value("Delivery Note", self.delivery_note, "vi_versandsendung") == self.name:
			frappe.db.set_value(
				"Delivery Note",
				self.delivery_note,
				{"vi_versandsendung": None, "vi_sendungsnummer": None, "vi_tracking_url": None},
				update_modified=False,
			)


def _format_error(exc: CarrierError) -> str:
	msg = str(exc)
	details = getattr(exc, "messages", None)
	if details:
		msg += "\n\n" + "\n".join(f"• {d}" for d in details)
	return msg


def _notify_problem(doc):
	"""Desk-Benachrichtigung (und optional E-Mail) bei Zustellproblem/Retoure."""
	try:
		settings = frappe.get_cached_doc("Versand Integration Settings")
	except frappe.DoesNotExistError:
		return
	if not cint(settings.tracking_notify_problems):
		return

	if doc.tracking_problem_notified == doc.tracking_status:
		return

	role = settings.tracking_notify_role or "Stock Manager"
	users = [
		u
		for u in frappe.get_all(
			"Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent"
		)
		if frappe.db.get_value("User", u, "enabled")
	]
	if not users:
		return

	subject = _("Versand: {0} – {1}").format(doc.tracking_status, doc.shipment_number or doc.name)
	message = _("Sendung {0} ({1}, {2}): {3}").format(
		doc.name, doc.carrier, doc.customer_name or "", doc.tracking_status_text or doc.tracking_status
	)
	for user in users:
		frappe.get_doc(
			{
				"doctype": "Notification Log",
				"subject": subject,
				"email_content": message,
				"for_user": user,
				"type": "Alert",
				"document_type": "Versandsendung",
				"document_name": doc.name,
			}
		).insert(ignore_permissions=True)

	if cint(settings.tracking_notify_email):
		recipients = [frappe.db.get_value("User", u, "email") or u for u in users]
		frappe.sendmail(
			recipients=recipients,
			subject=subject,
			message=f"{message}<br><br>{get_url_to_form('Versandsendung', doc.name)}",
			reference_doctype="Versandsendung",
			reference_name=doc.name,
		)

	frappe.db.set_value(
		"Versandsendung", doc.name, "tracking_problem_notified", doc.tracking_status, update_modified=False
	)
