from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    Image,
    TableStyle,
)


REPORT_DIR = Path("reports")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

PDF_REPORT_FILE = REPORT_DIR / "MIP_PRO_Daily_Intelligence_Report_v11_5_Production.pdf"
LOGO_FILE = Path("static/images/mip_pro_logo.png")


def _safe_text(value: Any, default: str = "Not available") -> str:
    if value is None or value == "":
        return default

    return str(value)


def _currency(value: Any) -> str:
    try:
        return f"KSh {float(value):,.2f}"
    except (TypeError, ValueError):
        return "KSh 0.00"


def _add_page_number(canvas, document) -> None:
    canvas.saveState()

    canvas.setStrokeColor(colors.HexColor("#D9E3DC"))
    canvas.line(
        18 * mm,
        15 * mm,
        A4[0] - 18 * mm,
        15 * mm,
    )

    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#5E6A63"))

    canvas.drawString(
        18 * mm,
        10.5 * mm,
        "Powered by MIP Inc. | "
        "AI Investment Intelligence for Africa",
    )

    canvas.drawRightString(
        A4[0] - 18 * mm,
        10.5 * mm,
        f"MIP PRO V11.5 Production | Page {document.page}",
    )

    canvas.restoreState()


def generate_daily_report(
    market: Dict[str, Any],
    committee: Dict[str, Any],
    portfolio: Dict[str, Any],
    assistant: Dict[str, Any],
) -> Dict[str, str]:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    document = SimpleDocTemplate(
        str(PDF_REPORT_FILE),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title="MIP PRO Daily Intelligence Report",
        author="MIP PRO",
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        alignment=TA_CENTER,
        spaceAfter=8,
    )

    brand_style = ParagraphStyle(
        "BrandName",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#111111"),
        spaceAfter=4,
    )

    edition_style = ParagraphStyle(
        "BrandEdition",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#B48C25"),
        spaceAfter=10,
    )

    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#555555"),
        spaceAfter=16,
    )

    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#08783F"),
        spaceBefore=10,
        spaceAfter=8,
    )

    body_style = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        spaceAfter=6,
    )

    story = []

    if LOGO_FILE.exists():
        logo = Image(str(LOGO_FILE), width=42*mm, height=33.6*mm)
        logo.hAlign = "CENTER"
        story.append(logo)

    story.append(
        Paragraph(
            "MIP PRO",
            title_style,
        )
    )

    story.append(
        Paragraph(
            "Professional Intelligence Suite",
            subtitle_style,
        )
    )

    story.append(
        Paragraph(
            f"""
            Daily Market Intelligence Report<br/>
            Version 11.5 Production<br/>
            Generated: {generated_at}<br/>
            Powered by MIP Inc.<br/>
            AI Investment Intelligence for Africa
            """,
            subtitle_style,
        )
    )


    market_data = [
        ["Metric", "Value"],
        ["Market status", _safe_text(market.get("market_status"))],
        ["Average change", f"{market.get('average_change', 0)}%"],
        ["Securities analyzed", str(len(market.get("stocks", [])))],
        ["Data provider", _safe_text(market.get("provider"))],
    ]

    story.append(Paragraph("Market Overview", heading_style))
    story.append(_styled_table(market_data))

    committee_data = [
        ["Metric", "Value"],
        ["Decision", _safe_text(committee.get("final_decision"), "HOLD")],
        ["Confidence", f"{committee.get('confidence', 0)}%"],
        ["Summary", _safe_text(committee.get("summary"))],
    ]

    story.append(Paragraph("AI Investment Committee", heading_style))
    story.append(_styled_table(committee_data, widths=[45 * mm, 115 * mm]))

    portfolio_data = [
        ["Metric", "Value"],
        ["Total value", _currency(portfolio.get("total_value"))],
        ["Total cost", _currency(portfolio.get("total_cost"))],
        ["Profit / loss", _currency(portfolio.get("pnl"))],
        ["Portfolio return", f"{portfolio.get('pnl_pct', 0)}%"],
        ["Risk level", _safe_text(portfolio.get("risk_level"))],
    ]

    story.append(Paragraph("Portfolio Summary", heading_style))
    story.append(_styled_table(portfolio_data))

    story.append(Paragraph("Autonomous Assistant", heading_style))
    story.append(
        Paragraph(
            (
                f"<b>Action:</b> "
                f"{_safe_text(assistant.get('action'), 'HOLD / WATCH')}<br/>"
                f"<b>Confidence:</b> "
                f"{assistant.get('confidence', 0)}%<br/>"
                f"<b>Summary:</b> "
                f"{_safe_text(assistant.get('summary'))}"
            ),
            body_style,
        )
    )

    opportunities = assistant.get("ranked_opportunities", [])

    story.append(Paragraph("Top Opportunities", heading_style))

    if opportunities:
        opportunity_rows = [
            [
                "Rank",
                "Symbol",
                "Signal",
                "Score",
                "RSI",
                "MACD",
                "Trend",
            ]
        ]

        for index, item in enumerate(opportunities[:16], start=1):
            opportunity_rows.append(
                [
                    index,
                    _safe_text(item.get("symbol"), "UNKNOWN"),
                    _safe_text(item.get("signal"), "HOLD"),
                    item.get("score", 0),
                    item.get("rsi", 0),
                    item.get("macd", 0),
                    _safe_text(item.get("trend"), "Unknown"),
                ]
            )

        story.append(
            _styled_table(
                opportunity_rows,
                widths=[
                    12 * mm,
                    22 * mm,
                    25 * mm,
                    18 * mm,
                    18 * mm,
                    20 * mm,
                    45 * mm,
                ],
                font_size=8,
            )
        )
    else:
        story.append(
            Paragraph(
                "No ranked opportunities are currently available.",
                body_style,
            )
        )

    story.extend(
        [
            Spacer(1, 12),
            Paragraph(
                (
                    "<b>Disclaimer:</b> This report is for analytical "
                    "and educational purposes only. It is not financial "
                    "advice and does not guarantee future performance."
                ),
                body_style,
            ),
        ]
    )

    document.build(
        story,
        onFirstPage=_add_page_number,
        onLaterPages=_add_page_number,
    )

    return {
        "path": str(PDF_REPORT_FILE),
        "generated_at": generated_at,
        "format": "pdf",
    }


def _styled_table(
    data,
    widths=None,
    font_size: int = 9,
) -> Table:
    table = Table(
        data,
        colWidths=widths,
        repeatRows=1,
        hAlign="LEFT",
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#08783F"),
                ),
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white,
                ),
                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    "Helvetica-Bold",
                ),
                (
                    "FONTNAME",
                    (0, 1),
                    (-1, -1),
                    "Helvetica",
                ),
                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    font_size,
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.35,
                    colors.HexColor("#B8C2CC"),
                ),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [
                        colors.white,
                        colors.HexColor("#F3F6F8"),
                    ],
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
            ]
        )
    )

    return table
