import unittest

from tax_invoice.validator import (
    approved_candidates,
    find_duplicates,
    rows_from_values,
    validate_row,
)


VALID = {
    "요청ID": "REQ-001",
    "상태": "발행승인",
    "공급받는자_상호": "테스트 주식회사",
    "공급받는자_사업자번호": "123-45-67890",
    "공급받는자_대표자": "홍길동",
    "공급받는자_이메일": "billing@example.com",
    "작성일": "2026-07-20",
    "품목": "콘텐츠 제작비",
    "공급가액": "1000000",
    "세액": "100000",
    "합계금액": "1100000",
    "영수청구": "청구",
}


class ValidateRowTest(unittest.TestCase):
    def test_valid_approved_row_has_no_errors(self):
        self.assertEqual(validate_row(VALID), [])

    def test_rejects_missing_required_fields(self):
        row = dict(VALID)
        row["공급받는자_이메일"] = ""
        self.assertIn("공급받는자_이메일 누락", validate_row(row))

    def test_rejects_invalid_business_number(self):
        row = dict(VALID)
        row["공급받는자_사업자번호"] = "1234"
        self.assertIn("사업자번호 형식 오류", validate_row(row))

    def test_rejects_amount_mismatch(self):
        row = dict(VALID)
        row["합계금액"] = "1200000"
        self.assertIn("합계금액 불일치", validate_row(row))

    def test_rejects_invalid_email(self):
        row = dict(VALID)
        row["공급받는자_이메일"] = "not-an-email"
        self.assertIn("이메일 형식 오류", validate_row(row))


class BatchValidationTest(unittest.TestCase):
    def test_finds_duplicate_invoice_keys(self):
        second = dict(VALID, 요청ID="REQ-002")
        duplicates = find_duplicates([VALID, second])
        self.assertEqual(duplicates, {"REQ-001", "REQ-002"})

    def test_only_clean_approved_rows_are_candidates(self):
        pending = dict(VALID, 요청ID="REQ-002", 상태="검토대기")
        invalid = dict(VALID, 요청ID="REQ-003", 공급받는자_이메일="")
        self.assertEqual(approved_candidates([VALID, pending, invalid]), [VALID])

    def test_converts_sheet_values_to_named_rows(self):
        values = [["요청ID", "상태", "품목"], ["REQ-001", "발행승인", "제작비"]]
        self.assertEqual(
            rows_from_values(values),
            [{"요청ID": "REQ-001", "상태": "발행승인", "품목": "제작비"}],
        )

    def test_empty_sheet_has_no_rows(self):
        self.assertEqual(rows_from_values([]), [])


if __name__ == "__main__":
    unittest.main()
