import unittest

from tax_invoice.popbill_mapper import build_taxinvoice


ISSUER = {
    "corp_num": "6198703398",
    "corp_name": "주식회사 어라운딧 (AROUNDIT)",
    "ceo_name": "오대용",
    "addr": "서울특별시 마포구 포은로8길 29, 122호(망원동, 디콜라보)",
    "biz_type": "서비스, 정보통신업",
    "biz_class": "엔터테인먼트, 광고대행업, 영상제작, 미디어콘텐츠창작업",
    "contact_name": "오대용",
    "email": "account@aroumdit.co.kr",
}

ROW = {
    "요청ID": "REQ-20260720-001",
    "작성일": "2026-07-20",
    "공급받는자_상호": "테스트 주식회사",
    "공급받는자_사업자번호": "888-88-88888",
    "공급받는자_대표자": "홍길동",
    "공급받는자_주소": "서울시",
    "공급받는자_업태": "서비스",
    "공급받는자_종목": "광고업",
    "공급받는자_이메일": "",
    "품목": "콘텐츠 제작비",
    "공급가액": "1,000,000",
    "세액": "100,000",
    "합계금액": "1,100,000",
    "영수청구": "청구",
    "내부메모": "테스트",
}


class BuildTaxinvoiceTest(unittest.TestCase):
    def test_maps_sheet_row_to_popbill_taxinvoice(self):
        invoice = build_taxinvoice(ROW, ISSUER)
        self.assertEqual(invoice.invoicerCorpNum, "6198703398")
        self.assertEqual(invoice.invoicerEmail, "account@aroumdit.co.kr")
        self.assertEqual(invoice.invoiceeCorpNum, "8888888888")
        self.assertEqual(invoice.writeDate, "20260720")
        self.assertEqual(invoice.invoicerMgtKey, "REQ-20260720-001")
        self.assertEqual(invoice.supplyCostTotal, "1000000")
        self.assertEqual(invoice.taxTotal, "100000")
        self.assertEqual(invoice.totalAmount, "1100000")
        self.assertEqual(invoice.purposeType, "청구")
        self.assertFalse(invoice.invoicerSMSSendYN)
        self.assertEqual(invoice.remark1, "")
        self.assertEqual(invoice.detailList[0].itemName, "콘텐츠 제작비")
        self.assertEqual(invoice.detailList[0].supplyCost, "1000000")
        self.assertEqual(invoice.detailList[0].remark, "")

    def test_removes_unsupported_chars_and_limits_management_key(self):
        row = dict(ROW, 요청ID="요청/2026/07/20/아주긴문서번호-0001")
        invoice = build_taxinvoice(row, ISSUER)
        self.assertRegex(invoice.invoicerMgtKey, r"^[A-Za-z0-9_-]{1,24}$")


if __name__ == "__main__":
    unittest.main()
