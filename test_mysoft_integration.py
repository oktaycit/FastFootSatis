import datetime
import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from integrations import IntegrationManager, MysoftProvider


class MysoftProviderTests(unittest.TestCase):
    def test_build_invoice_payload_maps_fastfoot_invoice(self):
        provider = MysoftProvider({
            "enabled": True,
            "company_tax_id": "1234567890",
            "draft": True,
        })

        payload = provider.build_invoice_payload({
            "masa": "Masa 1",
            "customer": "ABC Ltd",
            "invoice_pending": True,
            "invoice_document_type": 9006,
            "invoice_tax_id": "9876543210",
            "invoice_serial_no": "GIB2026000000001",
            "invoice_note": "Mysoft deneme",
            "payment_type": "Kredi Kartı",
            "total": 300.0,
            "ikram_total": 0,
            "timestamp": datetime.datetime(2026, 6, 9, 12, 30),
            "items": [
                {"urun": "Yemek", "adet": 2, "fiyat": 100.0},
                {"urun": "İçecek", "adet": 1, "fiyat": 100.0},
            ],
        })

        self.assertTrue(payload["draft"])
        self.assertEqual(payload["invoice_kind"], "EFATURA")
        self.assertEqual(payload["customer"]["tax_id"], "9876543210")
        self.assertEqual(payload["serial_no"], "GIB2026000000001")
        self.assertEqual(payload["seller_tax_id"], "1234567890")
        self.assertEqual(len(payload["items"]), 2)
        self.assertEqual(payload["items"][0]["line_total"], 200.0)
        self.assertEqual(payload["items"][0]["vat_rate"], 10)
        self.assertEqual(payload["totals"]["payable"], 300.0)

    def test_build_invoice_payload_uses_configured_default_tax_rate(self):
        provider = MysoftProvider({
            "enabled": True,
            "company_tax_id": "1234567890",
            "draft": True,
        })

        payload = provider.build_invoice_payload({
            "masa": "Masa 1",
            "customer": "ABC Ltd",
            "invoice_pending": True,
            "invoice_document_type": 9006,
            "invoice_tax_id": "9876543210",
            "invoice_serial_no": "GIB2026000000001",
            "payment_type": "Kredi Kartı",
            "total": 300.0,
            "timestamp": datetime.datetime(2026, 6, 9, 12, 30),
            "default_tax_rate": 20,
            "items": [
                {"urun": "Yemek", "adet": 1, "fiyat": 300.0},
            ],
        })

        self.assertEqual(payload["items"][0]["vat_rate"], 20)

    def test_send_invoice_skips_non_invoice_sales(self):
        provider = MysoftProvider({"enabled": True, "base_url": "https://example.test", "invoice_endpoint": "/invoice"})

        result = provider.send_invoice({"invoice_pending": False})

        self.assertEqual(result, {"skipped": True})

    def test_send_invoice_posts_to_configured_endpoint(self):
        session = Mock()
        response = Mock()
        response.json.return_value = {"success": True, "id": "inv-1"}
        session.post.return_value = response
        requests_module = Mock()
        requests_module.Session.return_value = session

        with patch("integrations.requests", requests_module):
            provider = MysoftProvider({
                "enabled": True,
                "base_url": "https://mysoft.example",
                "invoice_endpoint": "/invoice/create",
                "api_key": "secret",
            })
            provider.authenticate()
            result = provider.send_invoice({
                "masa": "Masa 1",
                "customer": "ABC Ltd",
                "invoice_pending": True,
                "invoice_document_type": 9007,
                "invoice_tax_id": "11111111111",
                "invoice_serial_no": "ARS2026000000001",
                "payment_type": "Nakit",
                "total": 150.0,
                "items": [{"urun": "Yemek", "adet": 1, "fiyat": 150.0}],
            })

        self.assertEqual(result["id"], "inv-1")
        session.post.assert_called_once()
        self.assertEqual(session.post.call_args.args[0], "https://mysoft.example/invoice/create")
        self.assertEqual(session.post.call_args.kwargs["headers"]["X-API-Key"], "secret")
        self.assertEqual(session.post.call_args.kwargs["json"]["invoice_kind"], "EARSIV")


class IntegrationManagerTests(unittest.TestCase):
    def test_default_settings_include_mysoft(self):
        manager = IntegrationManager("/tmp/fastfoot-missing-integrations.json")

        accounting = manager.settings["accounting"]
        self.assertIn("mysoft", accounting)
        self.assertEqual(accounting["active_platform"], "none")
        self.assertEqual(accounting["mysoft"]["environment"], "test")
        self.assertIn("tenant_identifier_number", accounting["mysoft"])
        self.assertIn("invoice_series", accounting["mysoft"])
        self.assertIn("numbering_unit", accounting["mysoft"])
        self.assertIn("sender_alias", accounting["mysoft"])
        self.assertIn("receiver_alias", accounting["mysoft"])
        self.assertIn("xslt_code", accounting["mysoft"])

    def test_legacy_mysoft_settings_keep_new_default_fields(self):
        legacy_settings = {
            "accounting": {
                "active_platform": "none",
                "mysoft": {
                    "enabled": False,
                    "base_url": "https://mysoft.example",
                    "invoice_endpoint": "/invoice/create",
                },
            }
        }
        fd, path = tempfile.mkstemp(prefix="fastfoot-mysoft-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(legacy_settings, f)

            manager = IntegrationManager(path)
            mysoft = manager.settings["accounting"]["mysoft"]

            self.assertEqual(mysoft["base_url"], "https://mysoft.example")
            self.assertEqual(mysoft["environment"], "test")
            self.assertIn("tenant_identifier_number", mysoft)
            self.assertIn("invoice_series", mysoft)
            self.assertIn("numbering_unit", mysoft)
            self.assertIn("sender_alias", mysoft)
            self.assertIn("receiver_alias", mysoft)
            self.assertIn("xslt_code", mysoft)
        finally:
            try:
                os.remove(path)
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
