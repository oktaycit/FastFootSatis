import datetime
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
        self.assertEqual(payload["totals"]["payable"], 300.0)

    def test_send_invoice_skips_non_invoice_sales(self):
        provider = MysoftProvider({"enabled": True, "base_url": "https://example.test", "invoice_endpoint": "/invoice"})

        result = provider.send_invoice({"invoice_pending": False})

        self.assertEqual(result, {"skipped": True})

    @patch("integrations.requests.Session")
    def test_send_invoice_posts_to_configured_endpoint(self, session_cls):
        session = Mock()
        response = Mock()
        response.json.return_value = {"success": True, "id": "inv-1"}
        session.post.return_value = response
        session_cls.return_value = session

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


if __name__ == "__main__":
    unittest.main()
