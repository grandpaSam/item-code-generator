import frappe
from frappe.tests.utils import FrappeTestCase
from item_code_generation.item_variant.sku_generator import generate_variant_sku

class TestSkuGenerator(FrappeTestCase):

    def test_basic_substitution(self):
        doc = frappe._dict({
            "name": "TEST-001",
            "item_code": "TEST-001",
            "item_name": None,
            "variant_of": "RU{caliber}{color}",
            "attributes": [
                frappe._dict({"attribute": "Caliber", "attribute_value": "9mm"}),
                frappe._dict({"attribute": "Color", "attribute_value": "Black OD"}),
            ]
        })

        generate_variant_sku(doc)
        self.assertEqual(doc.item_code, "RU0009BKOD")

    def test_missing_sku_code_throws(self):
        doc = frappe._dict({
            "name": "TEST-002",
            "item_code": "TEST-002",
            "item_name": None,
            "variant_of": "RU{caliber}{color}",
            "attributes": [
                frappe._dict({"attribute": "Caliber", "attribute_value": "9mm"}),
                # color intentionally missing sku_code
            ]
        })

        with self.assertRaises(frappe.ValidationError):
            generate_variant_sku(doc)
