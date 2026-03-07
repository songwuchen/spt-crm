"""Utility for building PDF documents (quotes, contracts)."""
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Try to register a CJK font for Chinese text
_font_registered = False
_font_name = "Helvetica"
try:
    import os
    # Try common CJK font paths
    font_paths = [
        "C:/Windows/Fonts/msyh.ttc",     # 微软雅黑
        "C:/Windows/Fonts/simsun.ttc",    # 宋体
        "C:/Windows/Fonts/simhei.ttf",    # 黑体
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            pdfmetrics.registerFont(TTFont("CJK", fp))
            _font_name = "CJK"
            _font_registered = True
            break
except Exception:
    pass


def build_quote_pdf(
    quote_no: str,
    version_title: str,
    version_no: int,
    price_total: float,
    tax_rate: float,
    tax_total: float,
    discount_total: float,
    delivery_promise_date: str | None,
    validity_days: int | None,
    lines: list[dict],
    created_by_name: str,
    created_at: str,
) -> bytes:
    """Build a PDF for a quote version and return bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=20 * mm, bottomMargin=20 * mm)
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle("QTitle", parent=styles["Title"], fontName=_font_name, fontSize=18)
    normal_style = ParagraphStyle("QNormal", parent=styles["Normal"], fontName=_font_name, fontSize=10)
    header_style = ParagraphStyle("QHeader", parent=styles["Heading2"], fontName=_font_name, fontSize=13)

    elements = []

    # Title
    elements.append(Paragraph(f"报价单 {quote_no}", title_style))
    elements.append(Spacer(1, 4 * mm))

    # Meta info
    meta_lines = [
        f"版本: V{version_no} - {version_title}",
        f"总价: ¥{price_total:,.2f}",
    ]
    if tax_rate is not None:
        meta_lines.append(f"税率: {tax_rate * 100:.1f}%    税额: ¥{tax_total:,.2f}")
    if discount_total:
        meta_lines.append(f"折扣: ¥{discount_total:,.2f}")
    if delivery_promise_date:
        meta_lines.append(f"交付日期: {delivery_promise_date}")
    if validity_days:
        meta_lines.append(f"报价有效期: {validity_days} 天")
    meta_lines.append(f"创建人: {created_by_name}    日期: {created_at[:10] if created_at else ''}")

    for line in meta_lines:
        elements.append(Paragraph(line, normal_style))
    elements.append(Spacer(1, 6 * mm))

    # Line items table
    elements.append(Paragraph("报价明细", header_style))
    elements.append(Spacer(1, 3 * mm))

    header_row = ["序号", "类型", "物料编码", "名称", "规格", "数量", "单位", "单价", "金额"]
    table_data = [header_row]

    type_labels = {"standard": "标准", "nonstandard": "非标", "service": "服务", "spare": "备件"}
    for ln in lines:
        table_data.append([
            str(ln.get("line_no", "")),
            type_labels.get(ln.get("item_type", ""), ln.get("item_type", "")),
            str(ln.get("item_code", "") or ""),
            str(ln.get("item_name", "") or ""),
            str(ln.get("spec", "") or ""),
            f"{ln.get('qty', 0):.2f}" if ln.get("qty") else "",
            str(ln.get("unit", "") or ""),
            f"¥{ln.get('unit_price', 0):,.2f}" if ln.get("unit_price") else "",
            f"¥{ln.get('line_total', 0):,.2f}" if ln.get("line_total") else "",
        ])

    col_widths = [25, 35, 60, 80, 60, 40, 30, 55, 60]
    t = Table(table_data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), _font_name),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), _font_name),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("ALIGN", (5, 1), (8, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 6 * mm))

    # Total row
    elements.append(Paragraph(f"合计金额: ¥{price_total:,.2f}", header_style))

    doc.build(elements)
    return buf.getvalue()


def build_contract_pdf(
    contract_no: str,
    status: str,
    amount_total: float | None,
    signed_date: str | None,
    end_date: str | None,
    payment_terms: dict | None,
    delivery_terms: dict | None,
    created_by_name: str,
    created_at: str,
    version_no: int | None,
    version_title: str | None,
    key_clauses: dict | list | None,
) -> bytes:
    """Build a PDF for a contract and return bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=20 * mm, bottomMargin=20 * mm)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle("CTitle", parent=styles["Title"], fontName=_font_name, fontSize=18)
    normal_style = ParagraphStyle("CNormal", parent=styles["Normal"], fontName=_font_name, fontSize=10)
    header_style = ParagraphStyle("CHeader", parent=styles["Heading2"], fontName=_font_name, fontSize=13)

    elements = []

    elements.append(Paragraph(f"合同 {contract_no}", title_style))
    elements.append(Spacer(1, 4 * mm))

    status_labels = {"draft": "草稿", "signed": "已签署", "active": "执行中", "completed": "已完成", "terminated": "已终止"}
    meta_lines = [
        f"状态: {status_labels.get(status, status)}",
    ]
    if amount_total is not None:
        meta_lines.append(f"合同金额: ¥{amount_total:,.2f}")
    if signed_date:
        meta_lines.append(f"签署日期: {signed_date}")
    if end_date:
        meta_lines.append(f"到期日期: {end_date}")
    if version_no:
        meta_lines.append(f"当前版本: V{version_no} - {version_title or ''}")
    meta_lines.append(f"创建人: {created_by_name}    日期: {created_at[:10] if created_at else ''}")

    for line in meta_lines:
        elements.append(Paragraph(line, normal_style))
    elements.append(Spacer(1, 6 * mm))

    # Payment terms
    if payment_terms and isinstance(payment_terms, dict):
        elements.append(Paragraph("付款条款", header_style))
        elements.append(Spacer(1, 3 * mm))
        table_data = [["条款", "内容"]]
        for k, v in payment_terms.items():
            table_data.append([str(k), str(v or "")])
        t = Table(table_data, colWidths=[120, 340])
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), _font_name),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 6 * mm))

    # Delivery terms
    if delivery_terms and isinstance(delivery_terms, dict):
        elements.append(Paragraph("交付条款", header_style))
        elements.append(Spacer(1, 3 * mm))
        table_data = [["条款", "内容"]]
        for k, v in delivery_terms.items():
            table_data.append([str(k), str(v or "")])
        t = Table(table_data, colWidths=[120, 340])
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), _font_name),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 6 * mm))

    # Key clauses
    if key_clauses:
        elements.append(Paragraph("关键条款", header_style))
        elements.append(Spacer(1, 3 * mm))
        if isinstance(key_clauses, dict):
            for k, v in key_clauses.items():
                elements.append(Paragraph(f"<b>{k}</b>: {v}", normal_style))
        elif isinstance(key_clauses, list):
            for item in key_clauses:
                if isinstance(item, dict):
                    elements.append(Paragraph(f"· {item.get('clause', item.get('name', str(item)))}", normal_style))
                else:
                    elements.append(Paragraph(f"· {item}", normal_style))
        elements.append(Spacer(1, 6 * mm))

    doc.build(elements)
    return buf.getvalue()
