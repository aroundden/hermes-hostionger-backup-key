import re
from decimal import Decimal, InvalidOperation


REQUIRED_FIELDS = (
    "요청ID",
    "공급받는자_상호",
    "공급받는자_사업자번호",
    "공급받는자_대표자",
    "공급받는자_이메일",
    "작성일",
    "품목",
    "공급가액",
    "세액",
    "합계금액",
    "영수청구",
)


def _number(value):
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, AttributeError):
        return None


def validate_row(row):
    errors = []
    for field in REQUIRED_FIELDS:
        if not str(row.get(field, "")).strip():
            errors.append(f"{field} 누락")

    business_number = re.sub(r"\D", "", str(row.get("공급받는자_사업자번호", "")))
    if business_number and len(business_number) != 10:
        errors.append("사업자번호 형식 오류")

    email = str(row.get("공급받는자_이메일", "")).strip()
    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        errors.append("이메일 형식 오류")

    supply = _number(row.get("공급가액"))
    tax = _number(row.get("세액"))
    total = _number(row.get("합계금액"))
    if isinstance(supply, Decimal) and isinstance(tax, Decimal) and isinstance(total, Decimal):
        if supply + tax != total:
            errors.append("합계금액 불일치")

    return errors


def _duplicate_key(row):
    return (
        re.sub(r"\D", "", str(row.get("공급받는자_사업자번호", ""))),
        str(row.get("작성일", "")).strip(),
        str(row.get("품목", "")).strip(),
        str(_number(row.get("공급가액"))),
    )


def find_duplicates(rows):
    by_key = {}
    for row in rows:
        by_key.setdefault(_duplicate_key(row), []).append(str(row.get("요청ID", "")))
    return {request_id for ids in by_key.values() if len(ids) > 1 for request_id in ids}


def rows_from_values(values):
    if not values:
        return []
    headers = values[0]
    return [
        {header: row[index] if index < len(row) else "" for index, header in enumerate(headers)}
        for row in values[1:]
        if any(str(cell).strip() for cell in row)
    ]


def approved_candidates(rows):
    clean_approved = [
        row for row in rows
        if row.get("상태") == "발행승인" and not validate_row(row)
    ]
    duplicates = find_duplicates(clean_approved)
    return [
        row for row in clean_approved
        if str(row.get("요청ID")) not in duplicates
    ]
