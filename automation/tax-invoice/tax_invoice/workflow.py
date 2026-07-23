import hashlib
import json
from dataclasses import dataclass

from tax_invoice.popbill_mapper import management_key
from tax_invoice.validator import approved_candidates, find_duplicates, validate_row


@dataclass(frozen=True)
class Candidate:
    sheet_row: int
    request_id: str
    management_key: str
    row: dict


def analyze_rows(rows):
    duplicates = find_duplicates(rows)
    errors = {}
    for index, row in enumerate(rows, start=2):
        row_errors = validate_row(row)
        if str(row.get("요청ID", "")) in duplicates:
            row_errors = [*row_errors, "중복 가능성"]
        if row_errors:
            errors[index] = row_errors

    approved_ids = {str(row["요청ID"]) for row in approved_candidates(rows)}
    candidates = [
        Candidate(
            sheet_row=index,
            request_id=str(row["요청ID"]),
            management_key=management_key(row["요청ID"]),
            row=row,
        )
        for index, row in enumerate(rows, start=2)
        if str(row.get("요청ID", "")) in approved_ids
    ]
    return errors, candidates


def approval_token(candidates):
    snapshot = [
        {
            "sheet_row": c.sheet_row,
            "request_id": c.request_id,
            "management_key": c.management_key,
            "corp_num": c.row.get("공급받는자_사업자번호", ""),
            "write_date": c.row.get("작성일", ""),
            "supply": c.row.get("공급가액", ""),
            "tax": c.row.get("세액", ""),
            "total": c.row.get("합계금액", ""),
        }
        for c in candidates
    ]
    raw = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12].upper()
