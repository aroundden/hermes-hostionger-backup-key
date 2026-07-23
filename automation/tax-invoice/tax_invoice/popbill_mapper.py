import hashlib
import re

from popbill import Taxinvoice, TaxinvoiceDetail


def _digits(value):
    return re.sub(r"\D", "", str(value))


def _amount(value):
    return str(value).replace(",", "").strip()


def management_key(request_id):
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "", str(request_id))
    if not cleaned:
        cleaned = "REQ-" + hashlib.sha256(str(request_id).encode("utf-8")).hexdigest()[:16]
    return cleaned[:24]


def build_taxinvoice(row, issuer):
    write_date = _digits(row["작성일"])
    supply = _amount(row["공급가액"])
    tax = _amount(row["세액"])
    total = _amount(row["합계금액"])

    invoice = Taxinvoice(
        issueType="정발행",
        taxType="과세",
        chargeDirection="정과금",
        writeDate=write_date,
        purposeType=row.get("영수청구") or "청구",
        supplyCostTotal=supply,
        taxTotal=tax,
        totalAmount=total,
        invoicerMgtKey=management_key(row["요청ID"]),
        invoicerCorpNum=_digits(issuer["corp_num"]),
        invoicerCorpName=issuer["corp_name"],
        invoicerCEOName=issuer["ceo_name"],
        invoicerAddr=issuer.get("addr", ""),
        invoicerBizType=issuer.get("biz_type", ""),
        invoicerBizClass=issuer.get("biz_class", ""),
        invoicerContactName=issuer.get("contact_name", issuer["ceo_name"]),
        invoicerTEL=issuer.get("tel", ""),
        invoicerHP="",
        invoicerEmail=issuer.get("email", ""),
        invoicerSMSSendYN=False,
        invoiceeType="사업자",
        invoiceeCorpNum=_digits(row["공급받는자_사업자번호"]),
        invoiceeCorpName=row["공급받는자_상호"],
        invoiceeCEOName=row["공급받는자_대표자"],
        invoiceeAddr=row.get("공급받는자_주소", ""),
        invoiceeBizType=row.get("공급받는자_업태", ""),
        invoiceeBizClass=row.get("공급받는자_종목", ""),
        invoiceeContactName1=row.get("공급받는자_담당자", ""),
        invoiceeTEL1=row.get("공급받는자_연락처", ""),
        invoiceeHP1="",
        invoiceeEmail1=row.get("공급받는자_이메일", ""),
        invoiceeSMSSendYN=False,
        # 발행대장의 내부메모는 거래처 세금계산서에 노출하지 않는다.
        remark1="",
        businessLicenseYN=False,
        bankBookYN=False,
    )
    invoice.detailList = [
        TaxinvoiceDetail(
            serialNum=1,
            purchaseDT=write_date,
            itemName=row["품목"],
            qty=1,
            unitCost=supply,
            supplyCost=supply,
            tax=tax,
            remark="",
        )
    ]
    return invoice
