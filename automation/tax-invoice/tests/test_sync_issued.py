import unittest
from types import SimpleNamespace

from sync_issued import current_status_values, desired_status_values


class SyncIssuedTest(unittest.TestCase):
    def test_builds_current_sheet_values(self):
        row = {"검증결과": "old", "팝빌문서번호": "REQ-1", "국세청승인번호": ""}
        self.assertEqual(current_status_values(row), ["old", "REQ-1", ""])

    def test_builds_latest_popbill_values_with_actual_sdk_field(self):
        row = {"요청ID": "REQ-1", "팝빌문서번호": "REQ-1"}
        info = SimpleNamespace(stateCode=304, ntsconfirmNum="NTS-123")
        self.assertEqual(
            desired_status_values(row, info),
            ["팝빌 상태 304 · 국세청 전송성공", "REQ-1", "NTS-123"],
        )


if __name__ == "__main__":
    unittest.main()
