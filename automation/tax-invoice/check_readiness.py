#!/usr/bin/env python3
import json
from pathlib import Path

from popbill import PopbillException, TaxinvoiceService

CREDENTIALS = Path.home() / ".hermes/integrations/popbill/credentials.json"


def check(service, credentials, name, fn):
    try:
        value = fn()
        if hasattr(value, "unitCost"):
            value = value.unitCost
        return {"ok": True, "value": str(value)}
    except PopbillException as exc:
        return {"ok": False, "code": exc.code, "message": exc.message}


def inspect_environment(credentials, production):
    # Popbill SDK's TaxinvoiceService is a singleton and caches its HTTPS
    # connection. Force a reconnect so test and production checks in the same
    # process never reuse the other environment's host connection.
    service = TaxinvoiceService(credentials["link_id"], credentials["secret_key"])
    service._PopbillBase__timeOut = 0
    service.IsTest = not production
    service.IPRestrictOnOff = True
    service.UseStaticIP = False
    service.UseGAIP = False
    corp_num = credentials["corp_num"]
    user_id = credentials["user_id"]
    return {
        "environment": "production" if production else "test",
        # 파트너 연동 API는 일반 팝빌 잔액이 아니라 파트너 포인트에서 차감된다.
        "partner_balance": check(
            service, credentials, "partner_balance", lambda: service.getPartnerBalance(corp_num)
        ),
        "unit_cost": check(
            service, credentials, "unit_cost", lambda: service.getUnitCost(corp_num)
        ),
        "charge_info": check(
            service, credentials, "charge_info", lambda: service.getChargeInfo(corp_num, user_id)
        ),
        "certificate_expire": check(
            service, credentials, "certificate_expire", lambda: service.getCertificateExpireDate(corp_num)
        ),
    }


def main():
    credentials = json.loads(CREDENTIALS.read_text())
    test = inspect_environment(credentials, production=False)
    production = inspect_environment(credentials, production=True)
    api_ready = all(item["ok"] for item in production.values() if isinstance(item, dict))
    balance = (
        float(production.get("partner_balance", {}).get("value", 0))
        if production.get("partner_balance", {}).get("ok")
        else 0
    )
    blockers = []
    if not api_ready:
        blockers.append("운영 API·단가·인증서 점검 실패")
    if balance <= 0:
        blockers.append("팝빌 파트너 포인트 잔액 0원")
    print(json.dumps({
        "corp_num_last4": credentials["corp_num"][-4:],
        "production_api_ready": api_ready,
        "production_issuance_ready": api_ready and balance > 0,
        "blocking_reasons": blockers,
        "test": test,
        "production": production,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
