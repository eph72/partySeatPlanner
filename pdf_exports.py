"""Black-and-white PDF exports for the current seating plan."""

from __future__ import annotations

import math
from pathlib import Path
import re

from reportlab import __file__ as reportlab_file
from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

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


def _unique_export_paths(
    folder: Path,
    display_name: str,
) -> tuple[Path, Path]:
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
    """Return the user-facing name for a table.

    The custom/user-defined table name is authoritative. If no usable name
    exists, fall back to the automatically generated "Table N" label.
    """

    name = plan.table_name(table_id).strip()

    if name:
        return name

    return f"Table {table_id + 1}"


def _fit_line(
    pdf: canvas.Canvas,
    text: str,
    max_width: float,
    start_size: float,
    font_name: str = FONT_REGULAR,
) -> tuple[str, float]:
    size = start_size

    while (
        size > 5.0
        and pdfmetrics.stringWidth(text, font_name, size) > max_width
    ):
        size -= 0.25

    if pdfmetrics.stringWidth(text, font_name, size) <= max_width:
        return text, size

    shortened = text

    while (
        shortened
        and pdfmetrics.stringWidth(
            f"{shortened}...",
            font_name,
            size,
        )
        > max_width
    ):
        shortened = shortened[:-1]

    return f"{shortened.rstrip()}...", size


def _name_lines(name: str) -> tuple[str, ...]:
    parts = name.split()

    if len(parts) < 2:
        return (name,)

    return (
        parts[0],
        " ".join(parts[1:]),
    )


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

    pdf.rect(
        x,
        y,
        seat_width,
        seat_height,
        fill=1,
        stroke=1,
    )

    if not guest:
        return

    lines = _name_lines(guest.name)

    line_height = min(
        7.5,
        seat_height * 0.34,
    )

    first_baseline = (
        y
        + seat_height / 2
        + (
            line_height
            * (len(lines) - 1)
            / 2
        )
        - 2.4
    )

    pdf.setFillColor(colors.black)

    for line_index, line in enumerate(lines):
        fitted, font_size = _fit_line(
            pdf,
            line,
            seat_width - 3 * mm,
            8.3,
        )

        pdf.setFont(
            FONT_REGULAR,
            font_size,
        )

        pdf.drawCentredString(
            x + seat_width / 2,
            first_baseline - line_index * line_height,
            fitted,
        )


def export_seating_plan(
    plan: SeatingPlan,
    output_path: Path,
) -> Path:
    """Export one large table per monochrome A3 landscape page."""

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    page_width, page_height = landscape(A3)

    pdf = canvas.Canvas(
        str(output_path),
        pagesize=(page_width, page_height),
    )

    pdf.setTitle("")
    pdf.setAuthor("")

    margin = 15 * mm
    title_y = page_height - 20 * mm

    stage_top = page_height - 43 * mm
    stage_bottom = 29 * mm

    block_height = stage_top - stage_bottom
    usable_width = page_width - 2 * margin

    gap = 3.0 * mm

    seat_height = min(
        24 * mm,
        block_height * 0.28,
    )

    table_height = min(
        32 * mm,
        block_height * 0.36,
    )

    table_count = max(
        1,
        plan.table_count,
    )

    for page_index, table_id in enumerate(
        range(table_count)
    ):
        # The user-defined table name is used directly here.
        label = _table_label(
            plan,
            table_id,
        )

        # --------------------------------------------------------------
        # Page title
        # --------------------------------------------------------------

        pdf.setFillColor(colors.black)
        pdf.setFont(FONT_BOLD, 22)

        fitted_title, title_size = _fit_line(
            pdf,
            label,
            page_width - 2 * margin,
            22,
            FONT_BOLD,
        )

        pdf.setFont(
            FONT_BOLD,
            title_size,
        )

        pdf.drawCentredString(
            page_width / 2,
            title_y,
            fitted_title,
        )

        pdf.setStrokeColor(
            colors.HexColor("#777777")
        )
        pdf.setLineWidth(0.6)

        pdf.line(
            margin,
            page_height - 28 * mm,
            page_width - margin,
            page_height - 28 * mm,
        )

        centre_y = (
            stage_top + stage_bottom
        ) / 2

        layout = plan.table_layout(
            table_id
        )

        seats_by_position = {
            seat.position: seat
            for seat in plan.seats
            if seat.table == table_id
        }

        # --------------------------------------------------------------
        # Round table
        # --------------------------------------------------------------

        if layout.shape == "round":
            seat_width = min(
                38 * mm,
                max(
                    18 * mm,
                    (
                        usable_width
                        / max(
                            1,
                            layout.capacity,
                        )
                    )
                    * 0.9,
                ),
            )

            round_seat_height = min(
                21 * mm,
                block_height * 0.19,
            )

            radius_x = min(
                145 * mm,
                usable_width / 2
                - seat_width / 2,
            )

            radius_y = min(
                53 * mm,
                block_height / 2
                - round_seat_height * 0.55,
            )

            body_width = body_height = min(
                72 * mm,
                block_height * 0.58,
            )

            pdf.setFillColor(colors.white)

            pdf.setStrokeColor(
                colors.HexColor("#555555")
            )

            pdf.setLineWidth(0.9)

            pdf.ellipse(
                page_width / 2
                - body_width / 2,
                centre_y
                - body_height / 2,
                page_width / 2
                + body_width / 2,
                centre_y
                + body_height / 2,
                fill=1,
                stroke=1,
            )

            # Use exactly the same user-facing table label inside the
            # round table as we use for the page title.
            pdf.setFillColor(colors.black)

            table_label, font_size = _fit_line(
                pdf,
                label,
                body_width - 8 * mm,
                12,
                FONT_BOLD,
            )

            pdf.setFont(
                FONT_BOLD,
                font_size,
            )

            pdf.drawCentredString(
                page_width / 2,
                centre_y
                - font_size * 0.35,
                table_label,
            )

            for position in range(
                layout.capacity
            ):
                angle = (
                    -math.pi / 2
                    + (
                        2
                        * math.pi
                        * position
                        / layout.capacity
                    )
                )

                x = (
                    page_width / 2
                    + math.cos(angle)
                    * radius_x
                    - seat_width / 2
                )

                y = (
                    centre_y
                    + math.sin(angle)
                    * radius_y
                    - round_seat_height / 2
                )

                seat = seats_by_position.get(
                    position
                )

                guest = (
                    plan.guests.get(
                        seat.guest_id
                    )
                    if seat
                    and seat.guest_id
                    else None
                )

                _draw_export_seat(
                    pdf,
                    guest,
                    x,
                    y,
                    seat_width,
                    round_seat_height,
                )

        # --------------------------------------------------------------
        # Rectangular table
        # --------------------------------------------------------------

        else:
            top_count = (
                layout.seat_count + 1
            ) // 2

            bottom_count = (
                layout.seat_count // 2
            )

            longest_side = max(
                1,
                top_count,
                bottom_count,
            )

            end_space = (
                34 * mm
                if layout.end_chairs
                else 0
            )

            side_width = (
                usable_width
                - 2 * end_space
            )

            seat_width = min(
                43 * mm,
                (
                    side_width
                    - (
                        longest_side - 1
                    )
                    * gap
                )
                / longest_side,
            )

            table_x = (
                margin + end_space
            )

            table_width = side_width

            table_y = (
                centre_y
                - table_height / 2
            )

            seat_offset = (
                table_height / 2
                + 5.5 * mm
            )

            top_y = (
                centre_y
                + seat_offset
            )

            bottom_y = (
                centre_y
                - seat_offset
                - seat_height
            )

            pdf.setFillColor(
                colors.white
            )

            pdf.setStrokeColor(
                colors.HexColor("#555555")
            )

            pdf.setLineWidth(0.9)

            pdf.rect(
                table_x,
                table_y,
                table_width,
                table_height,
                fill=1,
                stroke=1,
            )

            # User-defined table name inside the table body.
            pdf.setFillColor(
                colors.black
            )

            fitted_table_label, table_label_size = _fit_line(
                pdf,
                label,
                table_width - 10 * mm,
                12,
                FONT_BOLD,
            )

            pdf.setFont(
                FONT_BOLD,
                table_label_size,
            )

            pdf.drawCentredString(
                page_width / 2,
                centre_y - 4,
                fitted_table_label,
            )

            for position in range(
                layout.seat_count
            ):
                if position < top_count:
                    column = position
                    columns = top_count
                    y = top_y

                else:
                    column = (
                        bottom_count
                        - 1
                        - (
                            position
                            - top_count
                        )
                    )

                    columns = bottom_count
                    y = bottom_y

                span = (
                    columns - 1
                ) * (
                    seat_width + gap
                )

                x = (
                    page_width / 2
                    - span / 2
                    + column
                    * (
                        seat_width
                        + gap
                    )
                    - seat_width / 2
                )

                seat = seats_by_position.get(
                    position
                )

                guest = (
                    plan.guests.get(
                        seat.guest_id
                    )
                    if seat
                    and seat.guest_id
                    else None
                )

                _draw_export_seat(
                    pdf,
                    guest,
                    x,
                    y,
                    seat_width,
                    seat_height,
                )

            if layout.end_chairs:
                for position, x in (
                    (
                        layout.seat_count,
                        margin,
                    ),
                    (
                        layout.seat_count + 1,
                        page_width
                        - margin
                        - seat_width,
                    ),
                ):
                    seat = seats_by_position.get(
                        position
                    )

                    guest = (
                        plan.guests.get(
                            seat.guest_id
                        )
                        if seat
                        and seat.guest_id
                        else None
                    )

                    _draw_export_seat(
                        pdf,
                        guest,
                        x,
                        centre_y
                        - seat_height / 2,
                        seat_width,
                        seat_height,
                    )

        if (
            page_index
            < table_count - 1
        ):
            pdf.showPage()

    pdf.save()

    return output_path


def _guest_assignment(
    plan: SeatingPlan,
    guest_id: str,
) -> str:
    seat = plan.seat_for_guest(
        guest_id
    )

    if not seat:
        raise ValueError(
            "Only seated guests have an export assignment"
        )

    return _table_label(
        plan,
        seat.table,
    )


def _surname_sort_key(
    guest,
) -> tuple[str, str, str]:
    """Sort a guest by surname, then full name for stable tie-breaking."""

    words = re.findall(
        r"[^\W_]+(?:[-'][^\W_]+)*",
        guest.name,
        flags=re.UNICODE,
    )

    surname = (
        words[-1]
        if words
        else guest.name
    )

    return (
        surname.casefold(),
        guest.name.casefold(),
        guest.id,
    )


def _seated_guests(
    plan: SeatingPlan,
):
    return sorted(
        (
            guest
            for guest
            in plan.guests.values()
            if guest.attending
            and plan.seat_for_guest(
                guest.id
            )
            is not None
        ),
        key=_surname_sort_key,
    )


def export_guest_directory(
    plan: SeatingPlan,
    output_path: Path,
) -> Path:
    """Export a table-by-table guest directory."""

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    page_width, page_height = A4

    pdf = canvas.Canvas(
        str(output_path),
        pagesize=A4,
    )

    pdf.setTitle("Guest list")
    pdf.setAuthor("")

    margin_x = 11 * mm

    title_y = (
        page_height
        - 18 * mm
    )

    heading_y = (
        page_height
        - 31 * mm
    )

    first_name_y = (
        heading_y
        - 8 * mm
    )

    bottom_y = 14 * mm

    column_count = max(
        1,
        plan.table_count,
    )

    column_gap = 3 * mm

    column_width = (
        page_width
        - 2 * margin_x
        - (
            column_count - 1
        )
        * column_gap
    ) / column_count

    line_height = 5.4 * mm
    font_size = 8.2
    heading_size = 9.2

    table_guests = []

    for table_id in range(
        column_count
    ):
        table_guests.append(
            sorted(
                (
                    guest
                    for guest
                    in plan.guests.values()
                    if guest.attending
                    and (
                        seat := plan.seat_for_guest(
                            guest.id
                        )
                    )
                    is not None
                    and seat.table
                    == table_id
                ),
                key=_surname_sort_key,
            )
        )

    page_number = 0
    offsets = [0] * column_count

    while (
        page_number == 0
        or any(
            offset < len(guests)
            for offset, guests
            in zip(
                offsets,
                table_guests,
            )
        )
    ):
        pdf.setFillColor(
            colors.black
        )

        if page_number == 0:
            pdf.setFont(
                FONT_BOLD,
                22,
            )

            pdf.drawCentredString(
                page_width / 2,
                title_y,
                "Guest list",
            )

        for table_id, guests in enumerate(
            table_guests
        ):
            x = (
                margin_x
                + table_id
                * (
                    column_width
                    + column_gap
                )
            )

            pdf.setFillColor(
                colors.HexColor("#333333")
            )

            pdf.rect(
                x,
                heading_y - 4 * mm,
                column_width,
                7 * mm,
                fill=1,
                stroke=0,
            )

            pdf.setFillColor(
                colors.white
            )

            # Use the custom/user-facing table name for the heading.
            heading_text = _table_label(
                plan,
                table_id,
            )

            fitted_heading, fitted_heading_size = _fit_line(
                pdf,
                heading_text,
                column_width - 2 * mm,
                heading_size,
                FONT_BOLD,
            )

            pdf.setFont(
                FONT_BOLD,
                fitted_heading_size,
            )

            pdf.drawCentredString(
                x + column_width / 2,
                heading_y - 1.5 * mm,
                fitted_heading,
            )

            pdf.setStrokeColor(
                colors.HexColor("#CCCCCC")
            )

            pdf.setLineWidth(0.35)

            pdf.line(
                x,
                heading_y - 5.5 * mm,
                x + column_width,
                heading_y - 5.5 * mm,
            )

            pdf.setFillColor(
                colors.black
            )

            pdf.setFont(
                FONT_REGULAR,
                font_size,
            )

            y = first_name_y

            while (
                offsets[table_id]
                < len(guests)
                and y >= bottom_y
            ):
                guest = guests[
                    offsets[table_id]
                ]

                fitted, fitted_size = _fit_line(
                    pdf,
                    guest.name,
                    column_width - 2 * mm,
                    font_size,
                )

                pdf.setFont(
                    FONT_REGULAR,
                    fitted_size,
                )

                pdf.drawString(
                    x + 1 * mm,
                    y,
                    fitted,
                )

                offsets[table_id] += 1
                y -= line_height

        page_number += 1

        if any(
            offset < len(guests)
            for offset, guests
            in zip(
                offsets,
                table_guests,
            )
        ):
            pdf.showPage()

    pdf.save()

    return output_path


def export_pdf_bundle(
    plan: SeatingPlan,
    folder: Path,
    display_name: str,
) -> tuple[Path, Path]:
    """Create both requested PDFs without overwriting an earlier export."""

    folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    plan_path, guests_path = _unique_export_paths(
        folder,
        display_name,
    )

    export_seating_plan(
        plan,
        plan_path,
    )

    export_guest_directory(
        plan,
        guests_path,
    )

    return (
        plan_path,
        guests_path,
    )
