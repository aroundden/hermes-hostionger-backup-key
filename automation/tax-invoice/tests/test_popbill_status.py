import unittest
from types import SimpleNamespace

from tax_invoice.popbill_status import nts_confirm_num, status_message


class PopbillStatusTest(unittest.TestCase):
    def test_reads_actual_sdk_lowercase_confirmation_field(self):
        info = SimpleNamespace(ntsconfirmNum="202607214100020300003575")
        self.assertEqual(nts_confirm_num(info), "202607214100020300003575")

    def test_keeps_compatibility_with_alternate_field_name(self):
        info = SimpleNamespace(ntsConfirmNum="ALT")
        self.assertEqual(nts_confirm_num(info), "ALT")

    def test_labels_nts_success(self):
        info = SimpleNamespace(stateCode=304)
        self.assertEqual(status_message(info), "팝빌 상태 304 · 국세청 전송성공")


if __name__ == "__main__":
    unittest.main()