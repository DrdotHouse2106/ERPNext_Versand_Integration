import frappe

try:
	from frappe.tests import IntegrationTestCase as _TestCase
except ImportError:  # Frappe < 15
	from frappe.tests.utils import FrappeTestCase as _TestCase


class TestDHLSettings(_TestCase):
	def test_billing_number_must_be_14_digits(self):
		settings = frappe.get_single("DHL Settings")
		settings.billing_number = "123"
		with self.assertRaises(frappe.ValidationError):
			settings.validate()
		settings.billing_number = "33333333330101"
		settings.validate()  # darf nicht werfen

	def test_singleton_present(self):
		self.assertTrue(frappe.db.exists("DHL Settings", "DHL Settings"))
