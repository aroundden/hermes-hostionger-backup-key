#!/usr/bin/env python3
import argparse
import base64
import email.utils
import json
import mimetypes
import subprocess
from email.message import EmailMessage
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from tax_invoice.invoice_pdf import create_invoice_copy
from tax_invoice.validator import rows_from_values

SPREADSHEET_ID = "13cd3MPVCuQfO8InfcLN8V3IbUdbMUq5hzinYG04NIQM"
RANGE = "발행대장!A1:Y1000"
GOOGLE_API = Path.home() / ".hermes/skills/productivity/google-workspace/scripts/google_api.py"
HERMES_PYTHON = Path.home() / ".hermes/hermes-agent/venv/bin/python"
TOKEN = Path.home() / ".hermes/google_token.json"
ISSUER = Path(__file__).parent / "config/issuer.json"
ASSETS = Path.home() / ".hermes/integrations/popbill/assets"
OUTBOX = Path.home() / ".hermes/integrations/popbill/outbox"


def google_api(*args):
    result = subprocess.run(
        [str(HERMES_PYTHON), str(GOOGLE_API), *args],
        check=True,
        text=True,
        capture_output=True,
        timeout=120,
    )
    return json.loads(result.stdout)


def find_row(request_id):
    rows = rows_from_values(google_api("sheets", "get", SPREADSHEET_ID, RANGE))
    for sheet_row, row in enumerate(rows, start=2):
        if str(row.get("요청ID", "")).strip() == request_id:
            return sheet_row, row
    raise SystemExit(f"요청ID를 찾을 수 없습니다: {request_id}")


def existing_draft_for_thread(service, thread_id):
    page_token = None
    checked = 0
    while checked < 500:
        kwargs = {"userId": "me", "maxResults": 100}
        if page_token:
            kwargs["pageToken"] = page_token
        response = service.users().drafts().list(**kwargs).execute()
        drafts = response.get("drafts", [])
        checked += len(drafts)
        for draft in drafts:
            if draft.get("message", {}).get("threadId") == thread_id:
                return draft["id"]
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return None


def sender_address(service, fallback):
    aliases = service.users().settings().sendAs().list(userId="me").execute().get("sendAs", [])
    preferred = "account@aroumdit.co.kr"
    if any(item.get("sendAsEmail", "").lower() == preferred for item in aliases):
        return preferred
    return fallback


def later_sent_reply(service, thread_id, source_internal_date):
    thread = service.users().threads().get(userId="me", id=thread_id, format="metadata").execute()
    later = [
        message
        for message in thread.get("messages", [])
        if "SENT" in message.get("labelIds", [])
        and int(message.get("internalDate", 0)) > int(source_internal_date)
    ]
    if not later:
        return None
    return max(later, key=lambda message: int(message.get("internalDate", 0)))["id"]


def add_attachment(message, path):
    mime, _ = mimetypes.guess_type(path.name)
    maintype, subtype = (mime or "application/octet-stream").split("/", 1)
    message.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name)


def update_followup(sheet_row, source_message_id, draft_id, status):
    google_api(
        "sheets",
        "update",
        SPREADSHEET_ID,
        f"발행대장!W{sheet_row}:Y{sheet_row}",
        "--values",
        json.dumps([[source_message_id, draft_id, status]], ensure_ascii=False),
    )


def main():
    parser = argparse.ArgumentParser(description="발행완료 세금계산서의 Gmail 회신 초안 생성")
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--source-message-id", required=True)
    parser.add_argument("--create-draft", action="store_true", help="실제 Gmail 초안 생성 또는 기존 초안 연결")
    args = parser.parse_args()

    sheet_row, row = find_row(args.request_id)
    if str(row.get("상태", "")).strip() != "발행완료":
        raise SystemExit("발행완료 상태에서만 회신 초안을 만들 수 있습니다.")
    if not str(row.get("국세청승인번호", "")).strip():
        raise SystemExit("국세청 승인번호 동기화 후에만 회신 초안을 만들 수 있습니다.")

    issuer = json.loads(ISSUER.read_text())
    output_dir = OUTBOX / args.request_id
    invoice_pdf = create_invoice_copy(row, issuer, output_dir / f"{args.request_id}_전자세금계산서_사본.pdf")
    attachments = [
        invoice_pdf,
        ASSETS / "aroundit_business_registration.png",
        ASSETS / "aroundit_bank_account.pdf",
    ]
    missing = [str(path) for path in attachments if not path.exists()]
    if missing:
        raise SystemExit(f"첨부자료가 없습니다: {missing}")

    creds = Credentials.from_authorized_user_file(str(TOKEN))
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    source = service.users().messages().get(
        userId="me",
        id=args.source_message_id,
        format="metadata",
        metadataHeaders=["From", "Subject", "Message-ID", "References"],
    ).execute()
    headers = {header["name"].lower(): header["value"] for header in source["payload"].get("headers", [])}
    _, to_addr = email.utils.parseaddr(headers.get("from", ""))
    if not to_addr:
        raise SystemExit("원본 메일의 발신 주소를 확인할 수 없습니다.")
    thread_id = source["threadId"]
    sent_reply_id = later_sent_reply(service, thread_id, source.get("internalDate", 0))
    if sent_reply_id:
        if args.create_draft:
            update_followup(sheet_row, args.source_message_id, "", f"회신완료 확인 · {sent_reply_id}")
        print(json.dumps({
            "status": "already_replied",
            "request_id": args.request_id,
            "sent_message_id": sent_reply_id,
            "thread_id": thread_id,
            "sheet_updated": bool(args.create_draft),
        }, ensure_ascii=False, indent=2))
        return
    existing = existing_draft_for_thread(service, thread_id)
    if existing:
        if args.create_draft:
            update_followup(sheet_row, args.source_message_id, existing, "기존 회신초안 연결")
        print(json.dumps({
            "status": "existing_draft",
            "request_id": args.request_id,
            "draft_id": existing,
            "thread_id": thread_id,
            "sheet_updated": bool(args.create_draft),
        }, ensure_ascii=False, indent=2))
        return

    subject = headers.get("subject", "")
    if not subject.lower().startswith("re:"):
        subject = "Re: " + subject
    total = str(row.get("합계금액", ""))
    body = f"""안녕하세요.

요청주신 세금계산서는 {row.get('작성일', '')}자로 정상 발행되었으며, 국세청 전송도 완료되었습니다.
확인 편의를 위해 전자세금계산서 사본과 어라운딧 사업자등록증, 통장사본을 첨부드립니다.

- 공급받는자: {row.get('공급받는자_상호', '')}
- 품목: {row.get('품목', '')}
- 합계금액: {total}원

확인 부탁드립니다.

감사합니다.

오대용 드림
어라운딧(AROUNDit)
"""
    profile = service.users().getProfile(userId="me").execute()["emailAddress"]
    message = EmailMessage()
    message["To"] = to_addr
    message["From"] = sender_address(service, profile)
    message["Subject"] = subject
    if headers.get("message-id"):
        message["In-Reply-To"] = headers["message-id"]
        message["References"] = (headers.get("references", "") + " " + headers["message-id"]).strip()
    message.set_content(body)
    for attachment in attachments:
        add_attachment(message, attachment)

    report = {
        "status": "preview",
        "request_id": args.request_id,
        "thread_id": thread_id,
        "to": to_addr,
        "subject": subject,
        "attachments": [path.name for path in attachments],
    }
    if args.create_draft:
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        draft = service.users().drafts().create(
            userId="me",
            body={"message": {"raw": raw, "threadId": thread_id}},
        ).execute()
        draft_id = draft["id"]
        update_followup(sheet_row, args.source_message_id, draft_id, "회신초안 생성")
        report.update({"status": "created", "draft_id": draft_id, "sheet_updated": True})
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
