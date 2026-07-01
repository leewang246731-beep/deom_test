"""_order_json 补 buyer_nick 单测（mock DB，无 Docker）。"""
import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(__file__))

from app.api.consumer.orders import _order_json


class TestOrderJsonBuyerNick(unittest.TestCase):
    def _fake_order(self):
        o = MagicMock()
        o.id = 1
        o.order_no = "VM-1"
        o.buyer_id = 42
        o.total_amount = 100
        o.pay_amount = 100
        o.discount_amount = 0
        o.status = "paid"
        o.after_sale_status = None
        o.receiver_name = "小明"
        o.receiver_phone = "138"
        o.receiver_address = "南京"
        o.pay_time = None
        o.ship_time = None
        o.created_at = None
        return o

    def test_includes_buyer_nick(self):
        buyer = MagicMock()
        buyer.nickname = "测试买家小明"
        db = MagicMock()
        db.query.return_value.get.return_value = buyer  # VmBuyer 查询
        result = _order_json(self._fake_order(), [], db)
        self.assertEqual(result["buyer_nick"], "测试买家小明")

    def test_buyer_missing_fallback(self):
        db = MagicMock()
        db.query.return_value.get.return_value = None
        result = _order_json(self._fake_order(), [], db)
        self.assertEqual(result["buyer_nick"], "")


if __name__ == "__main__":
    unittest.main()
