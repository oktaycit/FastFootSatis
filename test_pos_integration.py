import unittest
from unittest.mock import patch

from pos_integration import POSManager


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code
        self.text = ""

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


class TokenBridgePayloadTests(unittest.TestCase):
    def test_token_bridge_payload_uses_token_units(self):
        manager = POSManager(True, "192.168.1.50", 8787, "token-bridge")

        payload = manager._create_token_bridge_payload(
            table_name="Masa 3",
            order_id="basket-1",
            items=[
                {"urun": "Kazandibi", "adet": 3, "fiyat": 175.00, "sectionNo": 3},
                {"urun": "Bardak Cay", "adet": 1, "fiyat": 30.00, "sectionNo": 2},
            ],
            payments=[
                {"type": "Kredi Kartı", "amount": 500.00},
                {"type": "Nakit", "amount": 55.00},
            ],
        )

        self.assertEqual(payload["basketID"], "basket-1")
        self.assertEqual(payload["items"][0]["price"], 17500)
        self.assertEqual(payload["items"][0]["quantity"], 3000)
        self.assertEqual(payload["items"][0]["total"], 52500000)
        self.assertEqual(payload["items"][0]["sectionNo"], 3)
        self.assertEqual(payload["items"][0]["taxPercent"], 1000)
        self.assertEqual(payload["paymentItems"][0]["type"], 3)
        self.assertEqual(payload["paymentItems"][0]["amount"], 50000)
        self.assertEqual(payload["paymentItems"][1]["type"], 1)
        self.assertEqual(payload["paymentItems"][1]["amount"], 5500)

    def test_token_bridge_rejects_mismatched_totals(self):
        manager = POSManager(True, "192.168.1.50", 8787, "token-bridge")

        with self.assertRaises(ValueError):
            manager._create_token_bridge_payload(
                table_name="Masa 3",
                items=[{"urun": "Kazandibi", "adet": 1, "fiyat": 175.00}],
                payments=[{"type": "Kredi Kartı", "amount": 174.00}],
            )

    def test_token_bridge_payload_uses_e_invoice_info_receipt(self):
        manager = POSManager(True, "192.168.1.50", 8787, "token-bridge")

        payload = manager._create_token_bridge_payload(
            table_name="Masa 3",
            order_id="invoice-basket-1",
            items=[{"urun": "Yemek", "adet": 1, "fiyat": 250.00}],
            payments=[{"type": "Kredi Kartı", "amount": 250.00}],
            invoice_pending=True,
            invoice_info={
                "document_type": 9006,
                "tax_id": "1234567890",
                "serial_no": "GIB2026000000001",
                "note": "ABC Ltd",
            },
        )

        self.assertEqual(payload["basketID"], "invoice-basket-1")
        self.assertEqual(payload["documentType"], 9006)
        self.assertFalse(payload["createInvoice"])
        self.assertEqual(payload["customerInfo"]["taxID"], "1234567890")
        self.assertEqual(payload["infoReceiptInfo"]["serialNo"], "GIB2026000000001")
        self.assertIn("ABC Ltd", payload["note"])

    def test_token_bridge_invoice_info_receipt_requires_tax_id_and_serial(self):
        manager = POSManager(True, "192.168.1.50", 8787, "token-bridge")

        with self.assertRaises(ValueError):
            manager._create_token_bridge_payload(
                table_name="Masa 3",
                items=[{"urun": "Yemek", "adet": 1, "fiyat": 250.00}],
                payments=[{"type": "Kredi Kartı", "amount": 250.00}],
                invoice_pending=True,
                invoice_info={"document_type": 9006, "tax_id": "", "serial_no": ""},
            )

    @patch("pos_integration.requests.post")
    def test_token_bridge_sale_posts_basket_to_windows_bridge(self, mock_post):
        mock_post.return_value = FakeResponse({
            "success": True,
            "receiptNo": 53,
            "zNo": 180,
        })
        manager = POSManager(True, "192.168.1.50", 8787, "token-bridge")

        success, message = manager.sale(
            30.00,
            "Masa 1",
            items=[{"urun": "Bardak Cay", "adet": 1, "fiyat": 30.00}],
            payments=[{"type": "Kredi Kartı", "amount": 30.00}],
            order_id="basket-2",
        )

        self.assertTrue(success)
        self.assertIn("Fiş: 53", message)
        mock_post.assert_called_once()
        self.assertEqual(mock_post.call_args.args[0], "http://192.168.1.50:8787/api/sale")
        self.assertEqual(mock_post.call_args.kwargs["json"]["basketID"], "basket-2")
        self.assertEqual(mock_post.call_args.kwargs["timeout"], 130)


if __name__ == "__main__":
    unittest.main()
