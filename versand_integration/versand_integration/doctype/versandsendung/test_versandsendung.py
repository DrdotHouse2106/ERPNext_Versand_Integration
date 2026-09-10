try:
	from frappe.tests import IntegrationTestCase as _TestCase
except ImportError:  # Frappe < 15
	from frappe.tests.utils import FrappeTestCase as _TestCase

from versand_integration.carriers.deutsche_post.signature import partner_signature, request_timestamp
from versand_integration.carriers.dhl.mapper import split_street, to_alpha3
from versand_integration.carriers.dpd.mapper import _weight_10g


class TestVersandsendung(_TestCase):
	def test_split_street(self):
		self.assertEqual(split_street("Musterstraße 12a"), ("Musterstraße", "12a"))
		self.assertEqual(split_street("Kurt-Schumacher-Str. 20"), ("Kurt-Schumacher-Str.", "20"))
		self.assertEqual(split_street("Am Hang"), ("Am Hang", ""))

	def test_to_alpha3(self):
		self.assertEqual(to_alpha3("DE"), "DEU")
		self.assertEqual(to_alpha3("DEU"), "DEU")

	def test_dpd_weight_10g(self):
		self.assertEqual(_weight_10g(3), 300)
		self.assertEqual(_weight_10g(0.35), 35)
		self.assertEqual(_weight_10g(0), 1)  # Mindestwert

	def test_dp_signature(self):
		# Deterministischer SHA-512-Hash über den bereinigten Keystring
		sig = partner_signature("PARID", "24032022-111000", "1", "geheim")
		self.assertEqual(len(sig), 128)
		self.assertEqual(sig, partner_signature("PARID", "24032022-111000", "1", "geheim"))
		self.assertRegex(request_timestamp(), r"^\d{8}-\d{6}$")
