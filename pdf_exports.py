"""Black-and-white PDF exports for the current seating plan."""

from __future__ import annotations

from datetime import datetime
import math
from pathlib import Path
import re
from xml.sax.saxutils import escape

from reportlab import __file__ as reportlab_file
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A3, A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from seat_planner_model import SeatingPlan


def _register_fonts() -> tuple[str, str]:
    fonts_folder = Path(reportlab_file).resolve().parent / "fonts"
    regular = fonts_folder / "Vera.ttf"
    bold = fonts_folder / "VeraBd.ttf"
    if regular.exists() and bold.exists():
        if "PSP-Vera" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("PSP-Vera", regular))
            pdfmetrics.registerFont(TTFont("PSP-Vera-Bold", bold))
        return "PSP-Vera", "PSP-Vera-Bold"
    return "Helvetica", "Helvetica-Bold"


FONT_REGULAR, FONT_BOLD = _register_fonts()


def _safe_stem(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9 _-]", "", value).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:60] or "Party seating"


def _unique_export_paths(folder: Path, display_name: str) -> tuple[Path, Path]:
    stem = _safe_stem(display_name)
    suffix = 1
    while True:
        numbered = stem if suffix == 1 else f"{stem} {suffix}"
        plan_path = folder / f"{numbered} - seating plan.pdf"
        guests_path = folder / f"{numbered} - guest list.pdf"
        if not plan_path.exists() and not guests_path.exists():
            return plan_path, guests_path
        suffix += 1


def _table_label(plan: SeatingPlan, table_id: int) -> str:
    number = f"Table {table_id + 1}"
    name = plan.table_name(table_id)
    return number if name.casefold() == number.casefold() else f"{number} - {name}"


def _fit_line(
    pdf: canvas.Canvas,
    text: str,
    max_width: float,
    start_size: float,
    font_name: str = FONT_REGULAR,
) -> tuple[str, float]:
    size = start_size
    while size > 5.0 and pdfmetrics.stringWidth(text, font_name, size) > max_width:
        size -= 0.25
    if pdfmetrics.stringWidth(text, font_name, size) <= max_width:
        return text, size
    shortened = text
    while shortened and pdfmetrics.stringWidth(f"{shortened}...", font_name, size) > max_width:
        shortened = shortened[:-1]
    return f"{shortened.rstrip()}...", size


def _name_lines(name: str) -> tuple[str, ...]:
    parts = name.split()
    if len(parts) < 2:
        return (name,)
    return (parts[0], " ".join(parts[1:]))


def _draw_export_seat(
    pdf: canvas.Canvas,
    guest,
    x: float,
    y: float,
    seat_width: float,
    seat_height: float,
) -> None:
    pdf.setFillColor(colors.white)
    pdf.setStrokeColor(colors.HexColor("#777777"))
    pdf.setLineWidth(0.55)
    pdf.rect(x, y, seat_width, seat_height, fill=1, stroke=1)
    if not guest:
        return
    lines = _name_lines(guest.name)
    line_height = min(7.5, seat_height * 0.34)
    first_baseline = y + seat_height / 2 + (line_height * (len(lines) - 1) / 2) - 2.4
    pdf.setFillColor(colors.black)
    for line_index, line in enumerate(lines):
        fitted, font_size = _fit_line(pdf, line, seat_width - 3 * mm, 7.2)
        pdf.setFont(FONT_REGULAR, font_size)
        pdf.drawCentredString(
            x + seat_width / 2,
            first_baseline - line_index * line_height,
            fitted,
        )


def export_seating_plan(plan: SeatingPlan, output_path: Path) -> Path:
    """Export four horizontal tables on one monochrome A3 landscape page."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    page_width, page_height = landscape(A3)
    pdf = canvas.Canvas(str(output_path), pagesize=(page_width, page_height))
    pdf.setTitle("Party Seating Plan")
    pdf.setAuthor("Party Seat Planner")

    margin = 15 * mm
    pdf.setFillColor(colors.black)
    pdf.setFont(FONT_BOLD, 20)
    pdf.drawString(margin, page_height - 18 * mm, "Party Seating Plan")
    pdf.setFont(FONT_REGULAR, 8)
    pdf.drawRightString(
        page_width - margin,
        page_height - 17 * mm,
        datetime.now().astimezone().strftime("Generated %d %B %Y, %H:%M"),
    )
    pdf.setStrokeColor(colors.HexColor("#777777"))
    pdf.setLineWidth(0.6)
    pdf.line(margin, page_height - 22 * mm, page_width - margin, page_height - 22 * mm)

    stage_top = page_height - 31 * mm
    stage_bottom = 23 * mm
    table_count = max(1, plan.table_count)
    block_height = (stage_top - stage_bottom) / table_count
    usable_width = page_width - 2 * margin
    gap = 2.1 * mm
    seat_height = min(11 * mm, block_height * 0.27)
    table_height = min(13 * mm, block_height * 0.25)

    for table_id in range(table_count):
        centre_y = stage_top - (table_id + 0.5) * block_height
        layout = plan.table_layout(table_id)
        seats_by_position = {
            seat.position: seat for seat in plan.seats if seat.table == table_id
        }
        if layout.shape == "round":
            seat_width = min(28 * mm, max(15 * mm, (215 * mm / layout.seat_count)))
            round_seat_height = min(9 * mm, block_height * 0.16)
            radius_x = min(118 * mm, usable_width / 2 - seat_width / 2)
            radius_y = min(23 * mm, block_height / 2 - round_seat_height * 0.55)
            body_width = body_height = min(34 * mm, block_height * 0.58)
            pdf.setFillColor(colors.white)
            pdf.setStrokeColor(colors.HexColor("#555555"))
            pdf.setLineWidth(0.9)
            pdf.ellipse(
                page_width / 2 - body_width / 2,
                centre_y - body_height / 2,
                page_width / 2 + body_width / 2,
                centre_y + body_height / 2,
                fill=1,
                stroke=1,
            )
            pdf.setFillColor(colors.black)
            pdf.setFont(FONT_BOLD, 8)
            pdf.drawCentredString(page_width / 2, centre_y + 1.5, f"Table {table_id + 1}")
            custom_name = plan.table_name(table_id)
            default_name = f"Table {table_id + 1}"
            if custom_name.casefold() != default_name.casefold():
                label, font_size = _fit_line(
                    pdf,
                    custom_name,
                    body_width - 5 * mm,
                    7,
                    FONT_REGULAR,
                )
                pdf.setFont(FONT_REGULAR, font_size)
                pdf.drawCentredString(page_width / 2, centre_y - 8, label)
            for position in range(layout.capacity):
                angle = -math.pi / 2 + (2 * math.pi * position / layout.capacity)
                x = page_width / 2 + math.cos(angle) * radius_x - seat_width / 2
                y = centre_y + math.sin(angle) * radius_y - round_seat_height / 2
                seat = seats_by_position.get(position)
                guest = plan.guests.get(seat.guest_id) if seat and seat.guest_id else None
                _draw_export_seat(pdf, guest, x, y, seat_width, round_seat_height)
            continue

        top_count = (layout.seat_count + 1) // 2
        bottom_count = layout.seat_count // 2
        longest_side = max(1, top_count, bottom_count)
        end_space = 28 * mm if layout.end_chairs else 0
        side_width = usable_width - 2 * end_space
        seat_width = min(34 * mm, (side_width - (longest_side - 1) * gap) / longest_side)
        table_x = margin + end_space
        table_width = side_width
        table_y = centre_y - table_height / 2
        seat_offset = table_height / 2 + 3.2 * mm
        top_y = centre_y + seat_offset
        bottom_y = centre_y - seat_offset - seat_height
        pdf.setFillColor(colors.white)
        pdf.setStrokeColor(colors.HexColor("#555555"))
        pdf.setLineWidth(0.9)
        pdf.rect(table_x, table_y, table_width, table_height, fill=1, stroke=1)
        pdf.setFillColor(colors.black)
        pdf.setFont(FONT_BOLD, 10)
        pdf.drawCentredString(page_width / 2, centre_y - 3.2, _table_label(plan, table_id))

        for position in range(layout.seat_count):
            if position < top_count:
                column = position
                columns = top_count
                y = top_y
            else:
                column = bottom_count - 1 - (position - top_count)
                columns = bottom_count
                y = bottom_y
            span = (columns - 1) * (seat_width + gap)
            x = page_width / 2 - span / 2 + column * (seat_width + gap) - seat_width / 2
            seat = seats_by_position.get(position)
            guest = plan.guests.get(seat.guest_id) if seat and seat.guest_id else None
            _draw_export_seat(pdf, guest, x, y, seat_width, seat_height)

        if layout.end_chairs:
            for position, x in (
                (layout.seat_count, margin),
                (layout.seat_count + 1, page_width - margin - seat_width),
            ):
                seat = seats_by_position.get(position)
                guest = plan.guests.get(seat.guest_id) if seat and seat.guest_id else None
                _draw_export_seat(
                    pdf,
                    guest,
                    x,
                    centre_y - seat_height / 2,
                    seat_width,
                    seat_height,
                )

    seated = sum(seat.guest_id is not None for seat in plan.seats)
    pdf.setFillColor(colors.black)
    pdf.setFont(FONT_REGULAR, 8)
    pdf.drawString(margin, 12 * mm, f"Seated guests: {seated}")
    pdf.drawRightString(page_width - margin, 12 * mm, "No colours or lock information shown")
    pdf.showPage()
    pdf.save()
    return output_path


def _guest_assignment(plan: SeatingPlan, guest_id: str) -> str:
    seat = plan.seat_for_guest(guest_id)
    if not seat:
        raise ValueError("Only seated guests have an export assignment")
    return _table_label(plan, seat.table)


def _seated_guests(plan: SeatingPlan):
    return sorted(
        (
            guest
            for guest in plan.guests.values()
            if guest.attending and plan.seat_for_guest(guest.id) is not None
        ),
        key=lambda item: (item.name.casefold(), item.id),
    )


def export_guest_directory(plan: SeatingPlan, output_path: Path) -> Path:
    """Export an alphabetical guest-to-table directory on A4 pages."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=17 * mm,
        title="Alphabetical Guest List",
        author="Party Seat Planner",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "PSPTitle",
        parent=styles["Title"],
        fontName=FONT_BOLD,
        fontSize=20,
        leading=24,
        textColor=colors.black,
        alignment=TA_LEFT,
        spaceAfter=4 * mm,
    )
    body_style = ParagraphStyle(
        "PSPBody",
        parent=styles["BodyText"],
        fontName=FONT_REGULAR,
        fontSize=9,
        leading=11,
        textColor=colors.black,
    )
    header_style = ParagraphStyle(
        "PSPHeader",
        parent=body_style,
        fontName=FONT_BOLD,
        textColor=colors.white,
    )

    seated_guests = _seated_guests(plan)
    story = [
        Paragraph("Alphabetical Guest List", title_style),
        Paragraph(
            f"{len(seated_guests)} seated guests",
            body_style,
        ),
        Spacer(1, 5 * mm),
    ]
    rows = [
        [Paragraph("Guest", header_style), Paragraph("Table", header_style)]
    ]
    for guest in seated_guests:
        rows.append(
            [
                Paragraph(escape(guest.name), body_style),
                Paragraph(escape(_guest_assignment(plan, guest.id)), body_style),
            ]
        )

    table = Table(rows, colWidths=[105 * mm, 70 * mm], repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#333333")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#AAAAAA")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F2F2")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(table)

    def add_page_footer(pdf: canvas.Canvas, doc) -> None:
        pdf.saveState()
        pdf.setStrokeColor(colors.HexColor("#AAAAAA"))
        pdf.setLineWidth(0.4)
        pdf.line(16 * mm, 12 * mm, A4[0] - 16 * mm, 12 * mm)
        pdf.setFillColor(colors.black)
        pdf.setFont(FONT_REGULAR, 7.5)
        pdf.drawString(16 * mm, 8 * mm, "Party Seat Planner")
        pdf.drawRightString(A4[0] - 16 * mm, 8 * mm, f"Page {doc.page}")
        pdf.restoreState()

    document.build(story, onFirstPage=add_page_footer, onLaterPages=add_page_footer)
    return output_path


def export_pdf_bundle(
    plan: SeatingPlan,
    folder: Path,
    display_name: str,
) -> tuple[Path, Path]:
    """Create both requested PDFs without overwriting an earlier export."""

    folder.mkdir(parents=True, exist_ok=True)
    plan_path, guests_path = _unique_export_paths(folder, display_name)
    export_seating_plan(plan, plan_path)
    export_guest_directory(plan, guests_path)
    return plan_path, guests_path
