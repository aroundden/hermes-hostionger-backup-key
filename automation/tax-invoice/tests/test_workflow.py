import unittest

from tax_invoice.workflow import analyze_rows, approval_token


BASE = {
    "요청ID": "REQ-001",
    "상태": "발행승인",
    "작성일": "2026-07-20",
    "공급받는자_상호": "테스트 주식회사",
    "공급받는자_사업자번호": "888-88-88888",
    "공급받는자_대표자": "홍길동",
    "공급받는자_이메일": "billing@example.com",
    "품목": "콘텐츠 제작비",
    "공급가액": "1000",
    "세액": "100",
    "합계금액": "1100",
    "영수청구": "청구",
}


class WorkflowTest(unittest.TestCase):
    def test_builds_stable_candidate_and_token(self):
        errors, candidates = analyze_rows([BASE])
        self.assertEqual(errors, {})
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].sheet_row, 2)
        self.assertEqual(candidates[0].management_key, "REQ-001")
        self.assertEqual(approval_token(candidates), approval_token(candidates))
        self.assertRegex(approval_token(candidates), r"^[A-F0-9]{12}$")

    def test_rejects_duplicate_approved_rows(self):
        duplicate = dict(BASE, 요청ID="REQ-002")
        errors, candidates = analyze_rows([BASE, duplicate])
        self.assertEqual(candidates, [])
        self.assertIn("중복 가능성", errors[2])
        self.assertIn("중복 가능성", errors[3])

    def test_ignores_unapproved_row(self):
        errors, candidates = analyze_rows([dict(BASE, 상태="검토대기")])
        self.assertEqual(errors, {})
        self.assertEqual(candidates, [])


if __name__ == "__main__":
    unittest.main()
