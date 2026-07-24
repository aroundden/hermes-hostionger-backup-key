import base64
import json
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import websocket

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def _cdp(ws, method, params=None, counter=[0]):
    counter[0] += 1
    ident = counter[0]
    ws.send(json.dumps({"id": ident, "method": method, "params": params or {}}))
    while True:
        reply = json.loads(ws.recv())
        if reply.get("id") == ident:
            if "error" in reply:
                raise RuntimeError(reply["error"])
            return reply.get("result", {})


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def create_popbill_official_pdf(service, corp_num, user_id, management_key, output_path):
    """Render Popbill's authenticated official print view to a PDF.

    This intentionally renders the live Popbill-issued invoice form. It must not
    be replaced with a locally recreated confirmation-copy template.
    """
    output_path = Path(output_path)
    info = service.getInfo(corp_num, "SELL", management_key)
    detail = service.getDetailInfo(corp_num, "SELL", management_key)
    state_code = int(str(getattr(info, "stateCode", 0)))
    if state_code != 304:
        raise RuntimeError(f"국세청 전송성공(304) 상태에서만 원본 양식을 내보낼 수 있습니다: {state_code}")

    expected = [
        str(getattr(detail, "invoiceeCorpName", "")).strip(),
        "전자세금계산서",
    ]
    url = service.getPrintURL(corp_num, "SELL", management_key, user_id)
    port = _free_port()
    profile = Path(tempfile.mkdtemp(prefix="popbill-chrome-"))
    proc = subprocess.Popen(
        [
            CHROME,
            "--headless=new",
            "--disable-gpu",
            "--remote-allow-origins=*",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        version_url = f"http://127.0.0.1:{port}/json/version"
        for _ in range(100):
            try:
                urllib.request.urlopen(version_url, timeout=1).read()
                break
            except Exception:
                time.sleep(0.1)
        else:
            raise RuntimeError("Chrome DevTools did not start")

        request = urllib.request.Request(f"http://127.0.0.1:{port}/json/new", method="PUT")
        target = json.loads(urllib.request.urlopen(request, timeout=10).read())
        ws = websocket.create_connection(
            target["webSocketDebuggerUrl"],
            timeout=30,
            origin=f"http://127.0.0.1:{port}",
        )
        try:
            _cdp(ws, "Page.enable")
            _cdp(ws, "Runtime.enable")
            _cdp(ws, "Page.navigate", {"url": url})
            expression = " && ".join(
                f"document.body.innerText.includes({json.dumps(value, ensure_ascii=False)})"
                for value in expected
                if value
            )
            deadline = time.time() + 60
            while time.time() < deadline:
                result = _cdp(
                    ws,
                    "Runtime.evaluate",
                    {
                        "expression": f"Boolean(document.body && {expression})",
                        "returnByValue": True,
                    },
                )
                if result.get("result", {}).get("value") is True:
                    break
                time.sleep(0.5)
            else:
                raise RuntimeError("Popbill official invoice did not finish rendering")

            _cdp(
                ws,
                "Runtime.evaluate",
                {
                    "expression": "(() => { const s=document.createElement('style'); s.textContent='::-webkit-scrollbar{display:none!important;width:0!important;height:0!important}html,body,*{scrollbar-width:none!important}'; document.head.appendChild(s); document.documentElement.style.overflow='hidden'; document.body.style.overflow='hidden'; })()"
                },
            )
            _cdp(ws, "Emulation.setEmulatedMedia", {"media": "print"})
            printed = _cdp(
                ws,
                "Page.printToPDF",
                {
                    "printBackground": True,
                    "preferCSSPageSize": True,
                    "displayHeaderFooter": False,
                    "marginTop": 0,
                    "marginBottom": 0,
                    "marginLeft": 0,
                    "marginRight": 0,
                },
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(base64.b64decode(printed["data"]))
            return output_path
        finally:
            ws.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(profile, ignore_errors=True)
