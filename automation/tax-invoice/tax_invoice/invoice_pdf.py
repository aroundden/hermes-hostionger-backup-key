from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

FONT_PATH = "/System/Library/Fonts/Supplemental/AppleGothic.ttf"
FONT_NAME = "AppleGothic"


def _p(value, style):
    return Paragraph(str(value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), style)


def create_invoice_copy(row, issuer, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if FONT_NAME not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))

    normal = ParagraphStyle("normal", fontName=FONT_NAME, fontSize=8, leading=11)
    center = ParagraphStyle("center", parent=normal, alignment=TA_CENTER)
    white_center = ParagraphStyle("white_center", parent=center, textColor=colors.white)
    title = ParagraphStyle("title", parent=center, fontSize=18, leading=22)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=landscape(A4),
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=9 * mm,
        bottomMargin=9 * mm,
        title=f"{row.get('공급받는자_상호', '')} 전자세금계산서 사본",
    )

    supplier = [
        ["등록번호", issuer.get("corp_num", ""), "상호", issuer.get("corp_name", ""), "대표", issuer.get("ceo_name", "")],
        ["주소", issuer.get("addr", ""), "업태", issuer.get("biz_type", ""), "종목", issuer.get("biz_class", "")],
        ["이메일", issuer.get("email", ""), "담당자", issuer.get("contact_name", ""), "", ""],
    ]
    customer = [
        ["등록번호", row.get("공급받는자_사업자번호", ""), "상호", row.get("공급받는자_상호", ""), "대표", row.get("공급받는자_대표자", "")],
        ["주소", row.get("공급받는자_주소", ""), "업태", row.get("공급받는자_업태", ""), "종목", row.get("공급받는자_종목", "")],
        ["이메일", row.get("공급받는자_이메일", ""), "", "", "", ""],
    ]

    def party_table(label, data, color):
        body = [[_p(label, white_center), "", "", "", "", ""]] + [[_p(c, normal) for c in r] for r in data]
        table = Table(body, colWidths=[18 * mm, 42 * mm, 15 * mm, 55 * mm, 14 * mm, 33 * mm], rowHeights=[8 * mm, 10 * mm, 14 * mm, 10 * mm])
        table.setStyle(TableStyle([
            ("SPAN", (0, 0), (-1, 0)),
            ("BACKGROUND", (0, 0), (-1, 0), color),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
            ("GRID", (0, 0), (-1, -1), 0.5, color),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#f4f6f8")),
            ("BACKGROUND", (2, 1), (2, -1), colors.HexColor("#f4f6f8")),
            ("BACKGROUND", (4, 1), (4, -1), colors.HexColor("#f4f6f8")),
        ]))
        return table

    amount_data = [
        [_p("작성일", center), _p(row.get("작성일", ""), center), _p("공급가액", center), _p(row.get("공급가액", ""), center), _p("세액", center), _p(row.get("세액", ""), center), _p("합계", center), _p(row.get("합계금액", ""), center)],
        [_p("품목", center), _p(row.get("품목", ""), normal), "", "", _p("구분", center), _p(row.get("영수청구", ""), center), "", ""],
    ]
    amount_table = Table(amount_data, colWidths=[18 * mm, 35 * mm, 20 * mm, 32 * mm, 15 * mm, 30 * mm, 15 * mm, 32 * mm], rowHeights=[10 * mm, 12 * mm])
    amount_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#374151")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f4f6f8")),
        ("BACKGROUND", (2, 0), (2, 0), colors.HexColor("#f4f6f8")),
        ("BACKGROUND", (4, 0), (4, -1), colors.HexColor("#f4f6f8")),
        ("BACKGROUND", (6, 0), (6, 0), colors.HexColor("#f4f6f8")),
        ("SPAN", (1, 1), (3, 1)),
        ("SPAN", (5, 1), (7, 1)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    nts = row.get("국세청승인번호", "")
    story = [
        _p("전자세금계산서 사본", title),
        _p(f"국세청 승인번호: {nts}", center),
        Spacer(1, 4 * mm),
        party_table("공급자", supplier, colors.HexColor("#2563eb")),
        Spacer(1, 3 * mm),
        party_table("공급받는자", customer, colors.HexColor("#dc2626")),
        Spacer(1, 4 * mm),
        amount_table,
        Spacer(1, 4 * mm),
        _p("본 문서는 팝빌을 통해 발행되어 국세청 전송이 완료된 전자세금계산서의 확인용 사본입니다.", center),
    ]
    doc.build(story)
    return output_path
