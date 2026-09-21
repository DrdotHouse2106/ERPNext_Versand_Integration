import frappe

try:
	from frappe.tests import IntegrationTestCase as _TestCase
except ImportError:  # Frappe < 15
	from frappe.tests.utils import FrappeTestCase as _TestCase

from versand_integration.carriers import base as cbase
from versand_integration.carriers.dhl import constants as dhl_c
from versand_integration.carriers.dhl.carrier import strip_label_data
from versand_integration.carriers.dhl.mapper import build_order_payload, split_street, to_alpha3
from versand_integration.carriers.dhl.tracking import _refine
from versand_integration.carriers.dpd.mapper import _weight_10g
from versand_integration.carriers.dpd.pickup import next_business_days, resolve_shipping_date
from versand_integration.carriers.dpd.tracking import _classify
from versand_integration.carriers.exceptions import CarrierConfigError


def _absender(**overrides):
	"""ResolvedAbsender mit vollstaendiger Adresse, fuer die Mapper-Tests."""
	from versand_integration.absender import ResolvedAbsender

	values = {
		"source": "Test",
		"name1": "Test Absender",
		"street": "Sträßchensweg",
		"house_number": "10",
		"postal_code": "53113",
		"city": "Bonn",
		"country": "DE",
		"_dhl_billing_fallback": "33333333330102",
	}
	values.update(overrides)
	return ResolvedAbsender(**values)


def _shipment(**overrides):
	doc = frappe.new_doc("Versandsendung")
	doc.update(
		{
			"carrier": "DHL",
			"receiver_name": "Max Mustermann",
			"receiver_street": "Kurt-Schumacher-Str.",
			"receiver_house_number": "20",
			"receiver_postal_code": "53113",
			"receiver_city": "Bonn",
			"receiver_country": "DE",
			"total_weight": 1.5,
		}
	)
	doc.update(overrides)
	return doc


class TestVersandsendung(_TestCase):
	# ------------------------------------------------------------ Hilfsfunktionen
	def test_split_street(self):
		self.assertEqual(split_street("Musterstraße 12a"), ("Musterstraße", "12a"))
		self.assertEqual(split_street("Kurt-Schumacher-Str. 20"), ("Kurt-Schumacher-Str.", "20"))
		self.assertEqual(split_street("Am Hang"), ("Am Hang", ""))

	def test_to_alpha3(self):
		self.assertEqual(to_alpha3("DE"), "DEU")
		self.assertEqual(to_alpha3("DEU"), "DEU")
		self.assertEqual(to_alpha3("Deutschland"), "DEU")
		with self.assertRaises(CarrierConfigError):
			to_alpha3("Absurdistan")

	def test_resolve_product(self):
		self.assertEqual(dhl_c.resolve_product("DHL Paket (national)"), "V01PAK")
		self.assertEqual(dhl_c.resolve_product("V01PAK"), "V01PAK")
		self.assertEqual(dhl_c.product_label("V53WPAK"), "DHL Paket International")
		with self.assertRaises(CarrierConfigError):
			dhl_c.resolve_product("Gibt es nicht")

	def test_dpd_weight_10g(self):
		self.assertEqual(_weight_10g(3), 300)
		self.assertEqual(_weight_10g(0.35), 35)
		self.assertEqual(_weight_10g(0), 1)  # Mindestwert

	# ------------------------------------------------------------ Gewichtspruefung
	def test_weight_required(self):
		with self.assertRaises(frappe.ValidationError):
			_shipment(total_weight=0)._ensure_weight()

	def test_weight_not_required_for_letters(self):
		doc = _shipment(carrier="Deutsche Post", total_weight=0)
		doc._ensure_weight()  # darf nicht werfen: Gewicht steckt im Produktcode

	def test_weight_summed_from_packages(self):
		doc = _shipment(total_weight=0)
		doc.append("packages", {"weight_kg": 1.2})
		doc.append("packages", {"weight_kg": 0.8})
		doc._ensure_weight()
		self.assertEqual(doc.total_weight, 2.0)

	# ------------------------------------------------------------ DHL-Payload
	def test_build_order_payload(self):
		settings = frappe._dict({"environment": "Sandbox", "profile": None, "default_product": None})
		payload = build_order_payload(settings, _shipment(), _absender())
		shipment = payload["shipments"][0]
		self.assertEqual(payload["profile"], dhl_c.DEFAULT_PROFILE)
		self.assertEqual(shipment["product"], "V01PAK")
		self.assertEqual(shipment["billingNumber"], "33333333330102")
		self.assertEqual(shipment["shipper"]["country"], "DEU")
		self.assertEqual(shipment["consignee"]["addressHouse"], "20")
		self.assertEqual(shipment["details"]["weight"], {"uom": "kg", "value": 1.5})

	def test_build_order_payload_one_shipment_per_package(self):
		settings = frappe._dict({"environment": "Sandbox", "profile": None, "default_product": None})
		doc = _shipment()
		doc.append("packages", {"weight_kg": 1})
		doc.append("packages", {"weight_kg": 2})
		payload = build_order_payload(settings, doc, _absender())
		self.assertEqual(len(payload["shipments"]), 2)

	def test_incomplete_sender_is_rejected(self):
		settings = frappe._dict({"environment": "Sandbox", "profile": None, "default_product": None})
		with self.assertRaises(CarrierConfigError):
			build_order_payload(settings, _shipment(), _absender(city=""))

	def test_dhl_retoure_needs_billing_number(self):
		settings = frappe._dict({"environment": "Sandbox", "profile": None, "default_product": None})
		with self.assertRaises(CarrierConfigError):
			build_order_payload(settings, _shipment(service_dhl_retoure=1), _absender())

	def test_strip_label_data(self):
		body = {"items": [{"shipmentNo": "222", "label": {"b64": "AAAA", "fileFormat": "PDF"}}]}
		stripped = strip_label_data(body)
		self.assertNotIn("AAAA", str(stripped))
		self.assertEqual(stripped["items"][0]["shipmentNo"], "222")
		self.assertEqual(stripped["items"][0]["label"]["fileFormat"], "PDF")
		self.assertEqual(body["items"][0]["label"]["b64"], "AAAA")  # Original unveraendert


class TestTracking(_TestCase):
	def _apply(self, doc, **result_kwargs):
		return doc._apply_tracking_result(cbase.TrackingResult(**result_kwargs))

	def test_status_and_events_applied(self):
		doc = _shipment(shipment_number="00340434161094042557")
		changed = self._apply(
			doc,
			status=cbase.TRACK_IN_TRANSIT,
			status_text="Die Sendung wurde im Paketzentrum bearbeitet.",
			events=[cbase.TrackingEvent(event_time="2026-09-20 10:00:00", description="Paketzentrum")],
		)
		self.assertTrue(changed)
		self.assertEqual(doc.tracking_status, cbase.TRACK_IN_TRANSIT)
		self.assertEqual(len(doc.tracking_events), 1)

	def test_unknown_does_not_overwrite_known_status(self):
		"""Alte Sendungen fallen beim Carrier irgendwann auf 'unbekannt' zurueck -
		der zuletzt bekannte Status darf dadurch nicht verloren gehen."""
		doc = _shipment(shipment_number="1", tracking_status=cbase.TRACK_DELIVERED)
		changed = self._apply(doc, status=cbase.TRACK_UNKNOWN)
		self.assertFalse(changed)
		self.assertEqual(doc.tracking_status, cbase.TRACK_DELIVERED)
		self.assertEqual(doc.tracking_data_expired, 1)
		self.assertEqual(doc.tracking_polling_active, 0)

	def test_final_status_stops_polling(self):
		doc = _shipment(shipment_number="1", tracking_polling_active=1)
		self._apply(doc, status=cbase.TRACK_DELIVERED)
		self.assertEqual(doc.tracking_polling_active, 0)

	def test_non_final_status_keeps_polling(self):
		doc = _shipment(shipment_number="1", tracking_polling_active=1)
		self._apply(doc, status=cbase.TRACK_IN_TRANSIT)
		self.assertEqual(doc.tracking_polling_active, 1)

	def test_status_text_truncated(self):
		doc = _shipment(shipment_number="1")
		self._apply(doc, status=cbase.TRACK_IN_TRANSIT, status_text="x" * 500)
		self.assertEqual(len(doc.tracking_status_text), 280)

	def test_dhl_refine(self):
		self.assertEqual(
			_refine(cbase.TRACK_IN_TRANSIT, "Die Sendung ist im Zustellfahrzeug."),
			cbase.TRACK_OUT_FOR_DELIVERY,
		)
		self.assertEqual(
			_refine(cbase.TRACK_IN_TRANSIT, "Retoure an den Absender"), cbase.TRACK_RETURN
		)
		self.assertEqual(
			_refine(cbase.TRACK_IN_TRANSIT, "Die Sendung wurde abgeholt."), cbase.TRACK_PICKED_UP
		)

	def test_dpd_classify(self):
		self.assertEqual(_classify("Die Sendung wurde zugestellt"), cbase.TRACK_DELIVERED)
		self.assertEqual(_classify("Zustellung nicht möglich"), cbase.TRACK_PROBLEM)
		self.assertEqual(_classify(""), cbase.TRACK_UNKNOWN)

	def test_tracking_status_options_match_constants(self):
		"""Die Select-Optionen am Dokument muessen exakt den normalisierten
		Status-Konstanten entsprechen - sonst schlaegt save() bei einem
		Status fehl, den nur der Carrier-Code kennt."""
		meta = frappe.get_meta("Versandsendung")
		options = {o for o in (meta.get_field("tracking_status").options or "").split("\n") if o}
		constants = {
			cbase.TRACK_ANNOUNCED,
			cbase.TRACK_PICKED_UP,
			cbase.TRACK_IN_TRANSIT,
			cbase.TRACK_OUT_FOR_DELIVERY,
			cbase.TRACK_DELIVERED,
			cbase.TRACK_PROBLEM,
			cbase.TRACK_RETURN,
			cbase.TRACK_UNKNOWN,
		}
		self.assertEqual(options, constants)


class TestDPDPickup(_TestCase):
	def test_business_days_skip_weekend(self):
		from frappe.utils import getdate

		# Freitag, 18.09.2026 -> Sa/So uebersprungen
		days = next_business_days(3, start=getdate("2026-09-18"))
		self.assertEqual([str(d) for d in days], ["2026-09-21", "2026-09-22", "2026-09-23"])

	def test_custom_date_required(self):
		with self.assertRaises(CarrierConfigError):
			resolve_shipping_date("Wunschtag", None)

	def test_unknown_option_rejected(self):
		with self.assertRaises(CarrierConfigError):
			resolve_shipping_date("Irgendwann", None)

	def test_sunday_shifted_to_monday(self):
		# 20.09.2026 ist ein Sonntag -> auf Montag verschoben
		self.assertEqual(resolve_shipping_date("Wunschtag", "2026-09-20"), "20260921")

	def test_no_option_means_no_override(self):
		self.assertIsNone(resolve_shipping_date(None))
