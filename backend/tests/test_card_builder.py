"""card_builder 纯函数单测（无 DB / 无 Docker 依赖）。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.card_builder import restore_vm_product_id


class TestRestoreVmProductId(unittest.TestCase):
    def test_valid_prefix(self):
        self.assertEqual(restore_vm_product_id("vm_785"), 785)

    def test_none(self):
        self.assertIsNone(restore_vm_product_id(None))

    def test_empty(self):
        self.assertIsNone(restore_vm_product_id(""))

    def test_no_prefix(self):
        self.assertIsNone(restore_vm_product_id("785"))

    def test_non_numeric_tail(self):
        self.assertIsNone(restore_vm_product_id("vm_abc"))


if __name__ == "__main__":
    unittest.main()
