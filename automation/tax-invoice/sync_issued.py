#!/usr/bin/env python3
import argparse
import json
import subprocess
from pathlib import Path

from popbill import PopbillException, TaxinvoiceService

from tax_invoice.popbill_mapper import management_key
from tax_invoice.popbill_status import nts_confirm_num, status_message
from tax_invoice.validator import rows_from_values

SPREADSHEET_ID = "13cd3MPVCuQfO8InfcLN8V3IbUdbMUq5hzinYG04NIQM"
RANGE = "발행대장!A1:V1000"
GOOGLE_API = Path.home() / ".hermes/skills/productivity/google-workspace/scripts/google_api.py"
HERMES_PYTHON = Path.home() / ".hermes/hermes-agent/venv/bin/python"
CREDENTIALS = Path.home() / ".hermes/integrations/popbill/credentials.json"


def google_api(*args):
    result = subprocess.run(
        [str(HERMES_PYTHON), str(GOOGLE_API), *args],
        check=True,
        text=True,
        capture_output=True,
        timeout=120,
    )
    return json.loads(result.stdout)


def service_for(credentials):
    service = TaxinvoiceService(credentials["link_id"], credentials["secret_key"])
    service.IsTest = False
    service.IPRestrictOnOff = True
    service.UseStaticIP = False
    service.UseGAIP = False
    return service


def desired_status_values(row, info):
    mgt_key = str(row.get("팝빌문서번호", "")).strip() or management_key(row["요청ID"])
    return [status_message(info), mgt_key, nts_confirm_num(info)]


def current_status_values(row):
    return [
        str(row.get("검증결과", "")),
        str(row.get("팝빌문서번호", "")),
        str(row.get("국세청승인번호", "")),
    ]


def main():
    parser = argparse.ArgumentParser(description="발행완료 세금계산서의 팝빌·국세청 상태 동기화")
    parser.add_argument("--write", action="store_true", help="변경된 상태를 발행대장에 기록")
    args = parser.parse_args()

    credentials = json.loads(CREDENTIALS.read_text())
    if credentials.get("is_test", True):
        raise SystemExit("운영 자격증명(is_test=false)에서만 동기화할 수 있습니다.")

    rows = rows_from_values(google_api("sheets", "get", SPREADSHEET_ID, RANGE))
    service = service_for(credentials)
    changes = []
    errors = []

    for sheet_row, row in enumerate(rows, start=2):
        if str(row.get("상태", "")).strip() != "발행완료":
            continue
        request_id = str(row.get("요청ID", "")).strip()
        mgt_key = str(row.get("팝빌문서번호", "")).strip() or management_key(request_id)
        try:
            info = service.getInfo(credentials["corp_num"], "SELL", mgt_key)
            desired = desired_status_values(row, info)
            current = current_status_values(row)
            if desired == current:
                continue
            change = {
                "sheet_row": sheet_row,
                "request_id": request_id,
                "before": current,
                "after": desired,
            }
            if args.write:
                google_api(
                    "sheets",
                    "update",
                    SPREADSHEET_ID,
                    f"발행대장!T{sheet_row}:V{sheet_row}",
                    "--values",
                    json.dumps([desired], ensure_ascii=False),
                )
                change["written"] = True
            changes.append(change)
        except PopbillException as exc:
            errors.append({"sheet_row": sheet_row, "request_id": request_id, "code": exc.code, "error": exc.message})
        except Exception as exc:
            errors.append({"sheet_row": sheet_row, "request_id": request_id, "error": str(exc)})

    print(json.dumps({
        "mode": "write" if args.write else "preview",
        "issued_rows": sum(1 for row in rows if str(row.get("상태", "")).strip() == "발행완료"),
        "change_count": len(changes),
        "changes": changes,
        "errors": errors,
    }, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
