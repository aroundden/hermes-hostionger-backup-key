STATE_LABELS = {
    100: "임시저장",
    200: "발행예정",
    300: "발행완료",
    301: "국세청 전송대기",
    302: "국세청 전송중",
    303: "국세청 전송실패",
    304: "국세청 전송성공",
}


def nts_confirm_num(info):
    """Return the NTS confirmation number across Popbill SDK naming variants."""
    return (
        getattr(info, "ntsconfirmNum", None)
        or getattr(info, "ntsConfirmNum", None)
        or ""
    )


def status_message(info):
    raw_state_code = getattr(info, "stateCode", None)
    try:
        state_code = int(str(raw_state_code))
    except (TypeError, ValueError):
        return f"팝빌 상태 {raw_state_code} · 상태 미확인"
    label = STATE_LABELS.get(state_code, "상태 미확인")
    return f"팝빌 상태 {state_code} · {label}"