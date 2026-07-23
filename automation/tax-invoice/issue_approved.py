#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path

from popbill import PopbillException, TaxinvoiceService

from tax_invoice.popbill_mapper import build_taxinvoice
from tax_invoice.popbill_status import nts_confirm_num, status_message
from tax_invoice.validator import rows_from_values
from tax_invoice.workflow import analyze_rows, approval_token

SPREADSHEET_ID = "13cd3MPVCuQfO8InfcLN8V3IbUdbMUq5hzinYG04NIQM"
RANGE = "발행대장!A1:Y1000"
GOOGLE_API = Path.home() / ".hermes/skills/productivity/google-workspace/scripts/google_api.py"
HERMES_PYTHON = Path.home() / ".hermes/hermes-agent/venv/bin/python"
CREDENTIALS = Path.home() / ".hermes/integrations/popbill/credentials.json"
ISSUER = Path(__file__).parent / "config/issuer.json"
POST_ISSUE_DRAFT = Path(__file__).parent / "post_issue_draft.py"
NOT_FOUND = -11000005


def google_api(*args):
    result = subprocess.run(
        [str(HERMES_PYTHON), str(GOOGLE_API), *args],
        check=True,
        text=True,
        capture_output=True,
        timeout=120,
    )
    return json.loads(result.stdout)


def load_rows():
    return rows_from_values(google_api("sheets", "get", SPREADSHEET_ID, RANGE))


def update_result(sheet_row, status, validation, mgt_key, nts_confirm_num=""):
    google_api(
        "sheets",
        "update",
        SPREADSHEET_ID,
        f"발행대장!E{sheet_row}:E{sheet_row}",
        "--values",
        json.dumps([[status]], ensure_ascii=False),
    )
    google_api(
        "sheets",
        "update",
        SPREADSHEET_ID,
        f"발행대장!T{sheet_row}:V{sheet_row}",
        "--values",
        json.dumps([[validation, mgt_key, nts_confirm_num]], ensure_ascii=False),
    )


def service_for(credentials, production):
    service = TaxinvoiceService(credentials["link_id"], credentials["secret_key"])
    service.IsTest = not production
    service.IPRestrictOnOff = True
    service.UseStaticIP = False
    service.UseGAIP = False
    return service


def create_followup_draft(candidate):
    source_message_id = str(candidate.row.get("원본메일ID", "")).strip()
    if not source_message_id:
        return {"status": "skipped", "reason": "원본메일ID 없음"}
    result = subprocess.run(
        [
            sys.executable,
            str(POST_ISSUE_DRAFT),
            "--request-id",
            candidate.request_id,
            "--source-message-id",
            source_message_id,
            "--create-draft",
        ],
        cwd=Path(__file__).parent,
        text=True,
        capture_output=True,
        timeout=180,
    )
    if result.returncode:
        return {"status": "failed", "error": (result.stderr or result.stdout).strip()}
    return json.loads(result.stdout)


def preview(rows):
    errors, candidates = analyze_rows(rows)
    return {
        "mode": "preview",
        "total_rows": len(rows),
        "validation_errors": {str(k): v for k, v in errors.items()},
        "candidate_count": len(candidates),
        "candidates": [
            {
                "sheet_row": c.sheet_row,
                "request_id": c.request_id,
                "management_key": c.management_key,
                "customer": c.row.get("공급받는자_상호", ""),
                "write_date": c.row.get("작성일", ""),
                "total": c.row.get("합계금액", ""),
            }
            for c in candidates
        ],
        "approval_token": approval_token(candidates) if candidates else None,
    }, candidates


def issue_candidates(candidates, token, production):
    expected = approval_token(candidates)
    if not candidates:
        raise SystemExit("발행 후보가 없습니다.")
    if token != expected:
        raise SystemExit(f"승인 토큰이 현재 후보 스냅샷과 다릅니다. 새 토큰: {expected}")
    if not production:
        raise SystemExit("발행대장 실행은 운영 환경에서만 허용됩니다.")

    credentials = json.loads(CREDENTIALS.read_text())
    if credentials.get("is_test", True):
        raise SystemExit(
            "자격증명이 안전모드(is_test=true)입니다. Den의 운영 전환 승인 후에만 false로 변경하세요."
        )
    issuer = json.loads(ISSUER.read_text())
    service = service_for(credentials, production=True)
    results = []

    for candidate in candidates:
        try:
            try:
                info = service.getInfo(credentials["corp_num"], "SELL", candidate.management_key)
                update_result(
                    candidate.sheet_row,
                    "발행완료",
                    status_message(info),
                    candidate.management_key,
                    nts_confirm_num(info),
                )
                results.append({
                    "request_id": candidate.request_id,
                    "status": "already_exists",
                    "state_code": getattr(info, "stateCode", None),
                    "followup": create_followup_draft(candidate),
                })
                continue
            except PopbillException as exc:
                if exc.code != NOT_FOUND:
                    raise

            response = service.registIssue(
                credentials["corp_num"],
                build_taxinvoice(candidate.row, issuer),
                False,
                False,
                None,
                "Den 승인형 자동발행",
                None,
                credentials["user_id"],
            )
            info = service.getInfo(credentials["corp_num"], "SELL", candidate.management_key)
            update_result(
                candidate.sheet_row,
                "발행완료",
                status_message(info),
                candidate.management_key,
                nts_confirm_num(info),
            )
            results.append({
                "request_id": candidate.request_id,
                "status": "issued",
                "result_code": getattr(response, "code", None),
                "state_code": getattr(info, "stateCode", None),
                "followup": create_followup_draft(candidate),
            })
        except Exception as exc:
            try:
                update_result(candidate.sheet_row, "발행실패", str(exc), candidate.management_key)
            except Exception as sheet_exc:
                results.append({
                    "request_id": candidate.request_id,
                    "status": "failed_and_sheet_update_failed",
                    "error": str(exc),
                    "sheet_error": str(sheet_exc),
                })
                continue
            results.append({"request_id": candidate.request_id, "status": "failed", "error": str(exc)})
    return results


def main():
    parser = argparse.ArgumentParser(description="승인형 팝빌 전자세금계산서 발행")
    parser.add_argument("--execute", action="store_true", help="실제 운영 발행 실행")
    parser.add_argument("--environment", choices=("test", "production"), default="test")
    parser.add_argument("--approval-token")
    parser.add_argument("--i-understand-legal-issuance", action="store_true")
    args = parser.parse_args()

    rows = load_rows()
    report, candidates = preview(rows)
    if not args.execute:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    if args.environment != "production" or not args.i_understand_legal_issuance:
        raise SystemExit(
            "실제 발행에는 --environment production과 --i-understand-legal-issuance가 모두 필요합니다."
        )
    if not args.approval_token:
        raise SystemExit("현재 후보 미리보기에서 생성된 --approval-token이 필요합니다.")
    results = issue_candidates(candidates, args.approval_token, production=True)
    print(json.dumps({"mode": "production_execute", "results": results}, ensure_ascii=False, indent=2))
    if any(result["status"].startswith("failed") for result in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
