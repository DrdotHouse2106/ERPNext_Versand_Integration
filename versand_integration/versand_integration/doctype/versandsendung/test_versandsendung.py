try:
	from frappe.tests import IntegrationTestCase as _TestCase
except ImportError:  # Frappe < 15
	from frappe.tests.utils import FrappeTestCase as _TestCase

from versand_integration.carriers.dhl.mapper import split_street, to_alpha3


class TestVersandsendung(_TestCase):
	def test_split_street(self):
		self.assertEqual(split_street("Musterstraße 12a"), ("Musterstraße", "12a"))
		self.assertEqual(split_street("Kurt-Schumacher-Str. 20"), ("Kurt-Schumacher-Str.", "20"))
		self.assertEqual(split_street("Am Hang"), ("Am Hang", ""))

	def test_to_alpha3(self):
		self.assertEqual(to_alpha3("DE"), "DEU")
		self.assertEqual(to_alpha3("DEU"), "DEU")
