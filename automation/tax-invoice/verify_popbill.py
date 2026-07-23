import json
from pathlib import Path

from popbill import PopbillException, TaxinvoiceService

CREDENTIALS = Path.home() / ".hermes/integrations/popbill/credentials.json"
config = json.loads(CREDENTIALS.read_text())
service = TaxinvoiceService(config["link_id"], config["secret_key"])
service.IsTest = bool(config.get("is_test", True))
service.IPRestrictOnOff = True
service.UseStaticIP = False
service.UseGAIP = False

try:
    balance = service.getBalance(config["corp_num"])
    charge = service.getChargeInfo(config["corp_num"], config["user_id"])
    contact = service.getContactInfo(config["corp_num"], config["user_id"], config["user_id"])
    print(json.dumps({
        "connected": True,
        "environment": "test" if service.IsTest else "production",
        "corp_num_last4": config["corp_num"][-4:],
        "balance": str(balance),
        "charge_method": getattr(charge, "unitCost", None),
        "contact_id": getattr(contact, "id", None),
        "contact_name": getattr(contact, "personName", None),
    }, ensure_ascii=False, indent=2))
except PopbillException as exc:
    print(json.dumps({
        "connected": False,
        "environment": "test" if service.IsTest else "production",
        "code": exc.code,
        "message": exc.message,
    }, ensure_ascii=False, indent=2))
    raise SystemExit(1)
