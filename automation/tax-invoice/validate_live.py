import json
import subprocess
from pathlib import Path

from tax_invoice.validator import approved_candidates, find_duplicates, rows_from_values, validate_row

SPREADSHEET_ID = "13cd3MPVCuQfO8InfcLN8V3IbUdbMUq5hzinYG04NIQM"
RANGE = "발행대장!A1:V1000"
GOOGLE_API = Path.home() / ".hermes/skills/productivity/google-workspace/scripts/google_api.py"
HERMES_PYTHON = Path.home() / ".hermes/hermes-agent/venv/bin/python"

result = subprocess.run(
    [str(HERMES_PYTHON), str(GOOGLE_API), "sheets", "get", SPREADSHEET_ID, RANGE],
    check=True,
    text=True,
    capture_output=True,
    timeout=120,
)
values = json.loads(result.stdout)
rows = rows_from_values(values)
duplicates = find_duplicates(rows)
errors = {
    str(row.get("요청ID", f"행-{index + 2}")): validate_row(row)
    for index, row in enumerate(rows)
    if validate_row(row)
}
candidates = approved_candidates(rows)

print(json.dumps({
    "전체건수": len(rows),
    "오류건수": len(errors),
    "중복요청ID": sorted(duplicates),
    "발행승인_정상건수": len(candidates),
    "오류상세": errors,
}, ensure_ascii=False, indent=2))
