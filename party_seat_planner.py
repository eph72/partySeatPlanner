#!/usr/bin/env python3
"""A polished visual party seating planner."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import platform
import random
import tkinter as tk
from tkinter import messagebox, simpledialog

from macos_pinch import attach_pinch
from seat_planner_model import (
    SaveManager,
    SeatingPlan,
    gender_database_available,
    read_guest_names,
)


APP_DIR = Path(__file__).resolve().parent

COLOUR = {
    "navy": "#17243A",
    "navy_2": "#223451",
    "ink": "#26344A",
    "muted": "#6F7C91",
    "canvas": "#F4F1EA",
    "paper": "#FFFFFF",
    "line": "#D8DDE6",
    "green": "#2D8B72",
    "green_hover": "#257660",
    "blue": "#4E79C7",
    "blue_hover": "#3C65AF",
    "orange": "#F39A3E",
    "orange_soft": "#FFF0DE",
    "bench": "#E2E4E8",
    "bench_line": "#BCC2CB",
    "absent": "#E9E9EB",
    "absent_text": "#9A9FA8",
    "danger": "#C85858",
    "male": "#BFD5F7",
    "male_line": "#88A9DD",
    "female": "#F3C4D7",
    "female_line": "#D991AE",
    "shadow": "#D9D5CC",
}


def offset_after_zoom(
    old_offset: float,
    old_zoom: float,
    new_zoom: float,
    focal_point: float,
    viewport_centre: float,
) -> float:
    """Return the offset that keeps one screen point fixed while zooming."""

    ratio = new_zoom / old_zoom
    return ratio * old_offset + (1 - ratio) * (focal_point - viewport_centre)


def runtime_compatibility_issue(
    system: str | None = None,
    tk_version: float | None = None,
) -> str | None:
    """Return a safe, actionable error before an incompatible Tk can crash."""

    system = system or platform.system()
    tk_version = tk.TkVersion if tk_version is None else tk_version
    if system == "Darwin" and tk_version < 8.6:
        return (
            f"This Python uses Tk {tk_version:.1f}, which can crash while opening windows on "
            "current macOS versions. Install a current Python 3.13 macOS installer from "
            "https://www.python.org/downloads/macos/, reopen Terminal, and try again."
        )
    return None


class PartySeatPlanner(tk.Tk):
    """Main application window and Canvas-based interaction layer."""

    def __init__(
        self,
        plan: SeatingPlan,
        guest_file: Path,
        enable_native_pinch: bool = True,
    ) -> None:
        super().__init__()
        self.plan = plan
        self.guest_file = guest_file
        self.save_manager = SaveManager(APP_DIR / "saves")

        self.title("Party Seat Planner")
        self.geometry("1500x940")
        self.minsize(1120, 720)
        self.configure(bg=COLOUR["navy"])

        self.seat_centres: dict[int, tuple[float, float]] = {}
        self.table_centres: dict[int, tuple[float, float]] = {}
        self.table_bounds: dict[int, tuple[float, float, float, float]] = {}
        self.bench_rect = (0.0, 0.0, 0.0, 0.0)
        self.absent_rect = (0.0, 0.0, 0.0, 0.0)
        self.zoom_factor = 1.0
        self.view_offset_x = 0.0
        self.view_offset_y = 0.0
        self._pinch_bridge = None
        self.drag_guest_id: str | None = None
        self.drag_table_id: int | None = None
        self.drag_offset = (0.0, 0.0)
        self.drag_items: list[int] = []
        self.bench_page = 0
        self.absent_page = 0
        self._redraw_job: str | None = None
        self._status_job: str | None = None

        self._build_layout()
        self._bind_canvas()
        self.after(80, self.draw_scene)
        self.after(120, self.refresh_saves)
        if enable_native_pinch:
            self.after(180, self._enable_native_pinch)
        else:
            self.after(
                180,
                lambda: self.set_status(
                    "Native pinch is disabled; use ⌘+scroll or ⌘+/− to zoom."
                ),
            )

    # ---------- layout ----------

    def _build_layout(self) -> None:
        self.sidebar = tk.Frame(self, bg=COLOUR["navy"], width=286)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        tk.Label(
            self.sidebar,
            text="PARTY",
            bg=COLOUR["navy"],
            fg="#8FA5C8",
            font=("Avenir Next", 11, "bold"),
        ).pack(anchor="w", padx=24, pady=(24, 0))
        tk.Label(
            self.sidebar,
            text="Seat Planner",
            bg=COLOUR["navy"],
            fg="white",
            font=("Avenir Next", 25, "bold"),
        ).pack(anchor="w", padx=22, pady=(0, 3))

        self.count_var = tk.StringVar()
        tk.Label(
            self.sidebar,
            textvariable=self.count_var,
            bg=COLOUR["navy"],
            fg="#AEBBD0",
            font=("Avenir Next", 10),
        ).pack(anchor="w", padx=24, pady=(0, 18))

        self._sidebar_button("Shuffle seats", self.randomise, COLOUR["green"], COLOUR["green_hover"])
        self._sidebar_button(
            "Alternate M / F", self.randomise_genders, COLOUR["blue"], COLOUR["blue_hover"]
        )
        self._sidebar_button("Edit guests", self.open_guest_editor, COLOUR["navy_2"], "#2C4264")

        tk.Frame(self.sidebar, height=1, bg="#33435C").pack(fill="x", padx=22, pady=16)

        saves_header = tk.Frame(self.sidebar, bg=COLOUR["navy"])
        saves_header.pack(fill="x", padx=22)
        tk.Label(
            saves_header,
            text="SAVED PLANS",
            bg=COLOUR["navy"],
            fg="#8FA5C8",
            font=("Avenir Next", 10, "bold"),
        ).pack(side="left")
        add = tk.Label(
            saves_header,
            text="＋ Save",
            bg=COLOUR["navy"],
            fg="white",
            cursor="hand2",
            font=("Avenir Next", 10, "bold"),
            padx=4,
            pady=3,
        )
        add.pack(side="right")
        add.bind("<Button-1>", lambda _event: self.save_current())
        add.bind("<Enter>", lambda _event: add.configure(bg=COLOUR["navy_2"]))
        add.bind("<Leave>", lambda _event: add.configure(bg=COLOUR["navy"]))

        saves_shell = tk.Frame(self.sidebar, bg=COLOUR["navy"])
        saves_shell.pack(fill="both", expand=True, padx=(17, 9), pady=(8, 8))
        self.saves_canvas = tk.Canvas(
            saves_shell, bg=COLOUR["navy"], highlightthickness=0, bd=0, width=240
        )
        saves_scroll = tk.Scrollbar(
            saves_shell, orient="vertical", command=self.saves_canvas.yview, width=10
        )
        self.saves_list = tk.Frame(self.saves_canvas, bg=COLOUR["navy"])
        self.saves_window = self.saves_canvas.create_window(
            (0, 0), window=self.saves_list, anchor="nw", width=245
        )
        self.saves_canvas.configure(yscrollcommand=saves_scroll.set)
        self.saves_canvas.pack(side="left", fill="both", expand=True)
        saves_scroll.pack(side="right", fill="y")
        self.saves_list.bind(
            "<Configure>",
            lambda _event: self.saves_canvas.configure(scrollregion=self.saves_canvas.bbox("all")),
        )
        self.saves_canvas.bind(
            "<Configure>", lambda event: self.saves_canvas.itemconfigure(self.saves_window, width=event.width)
        )

        status_frame = tk.Frame(self.sidebar, bg="#111C2F", height=72)
        status_frame.pack(fill="x", side="bottom")
        status_frame.pack_propagate(False)
        initial_status = "Drag names between seats. Right-click to lock."
        if not gender_database_available():
            initial_status = "Install requirements.txt for broad name recognition."
        self.status_var = tk.StringVar(value=initial_status)
        tk.Label(
            status_frame,
            textvariable=self.status_var,
            wraplength=240,
            justify="left",
            bg="#111C2F",
            fg="#CBD5E4",
            font=("Avenir Next", 9),
        ).pack(fill="both", expand=True, padx=20, pady=11)

        self.canvas = tk.Canvas(
            self,
            bg=COLOUR["canvas"],
            highlightthickness=0,
            bd=0,
            cursor="arrow",
        )
        self.canvas.pack(side="right", fill="both", expand=True)

    def _sidebar_button(self, text: str, command, colour: str, hover: str) -> tk.Label:
        button = tk.Label(
            self.sidebar,
            text=text,
            bg=colour,
            fg="white",
            cursor="hand2",
            font=("Avenir Next", 12, "bold"),
            padx=14,
            pady=11,
            anchor="w",
        )
        button.pack(fill="x", padx=22, pady=5)
        button.bind("<Enter>", lambda _event: button.configure(bg=hover))
        button.bind("<Leave>", lambda _event: button.configure(bg=colour))
        button.bind("<Button-1>", lambda _event: self._button_press(button, command))
        return button

    def _button_press(self, button: tk.Widget, command) -> None:
        original = button.cget("pady")
        button.configure(pady=max(8, int(original) - 2))
        self.after(85, lambda: button.winfo_exists() and button.configure(pady=original))
        command()

    def _bind_canvas(self) -> None:
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Double-Button-1>", self._on_double_click)
        self.canvas.bind("<Control-Button-1>", self._on_right_click)
        self.canvas.bind("<Button-2>", self._on_right_click)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<Command-MouseWheel>", self._on_zoom_wheel)
        self.canvas.bind("<Control-MouseWheel>", self._on_zoom_wheel)
        self.canvas.bind("<MouseWheel>", self._on_pan_wheel)
        self.canvas.bind("<Shift-MouseWheel>", self._on_horizontal_pan_wheel)
        self.bind("<Command-0>", self._reset_view)
        self.bind("<Control-0>", self._reset_view)
        self.bind("<Command-plus>", lambda event: self._keyboard_zoom(1.12, event))
        self.bind("<Command-equal>", lambda event: self._keyboard_zoom(1.12, event))
        self.bind("<Command-minus>", lambda event: self._keyboard_zoom(1 / 1.12, event))
        self.bind("<Control-plus>", lambda event: self._keyboard_zoom(1.12, event))
        self.bind("<Control-minus>", lambda event: self._keyboard_zoom(1 / 1.12, event))

    def _on_canvas_resize(self, _event) -> None:
        if self._redraw_job:
            self.after_cancel(self._redraw_job)
        self._redraw_job = self.after(40, self.draw_scene)

    def _enable_native_pinch(self) -> None:
        self._pinch_bridge = attach_pinch(self.canvas, self._on_native_pinch)
        if not self._pinch_bridge.available:
            self.set_status(
                "Native pinch was unavailable; use ⌘+scroll or ⌘+/− to zoom."
            )

    def _on_native_pinch(self, amount: float) -> None:
        x = self.canvas.winfo_pointerx() - self.canvas.winfo_rootx()
        y = self.canvas.winfo_pointery() - self.canvas.winfo_rooty()
        if not (0 <= x <= self.canvas.winfo_width() and 0 <= y <= self.canvas.winfo_height()):
            x = self.canvas.winfo_width() / 2
            y = self.canvas.winfo_height() / 2
        self._apply_zoom(max(0.82, min(1.18, 1.0 + amount)), x, y)

    def _on_zoom_wheel(self, event) -> str:
        delta = float(event.delta)
        steps = delta if abs(delta) < 20 else delta / 120
        self._apply_zoom(1.08 ** steps, event.x, event.y)
        return "break"

    def _keyboard_zoom(self, factor: float, _event=None) -> str:
        self._apply_zoom(
            factor,
            self.canvas.winfo_width() / 2,
            (58 + self.canvas.winfo_height() - 183) / 2,
        )
        return "break"

    def _on_pan_wheel(self, event) -> str:
        if self.zoom_factor <= 1.0:
            return "break"
        delta = float(event.delta)
        units = delta if abs(delta) < 20 else delta / 120
        self.view_offset_y += units * 14
        self._clamp_view_offset()
        self.draw_scene()
        return "break"

    def _on_horizontal_pan_wheel(self, event) -> str:
        if self.zoom_factor <= 1.0:
            return "break"
        delta = float(event.delta)
        units = delta if abs(delta) < 20 else delta / 120
        self.view_offset_x += units * 14
        self._clamp_view_offset()
        self.draw_scene()
        return "break"

    def _apply_zoom(self, factor: float, focal_x: float, focal_y: float) -> None:
        old_zoom = self.zoom_factor
        new_zoom = max(0.60, min(2.40, old_zoom * factor))
        if abs(new_zoom - old_zoom) < 0.0001:
            return
        width = max(self.canvas.winfo_width(), 700)
        height = max(self.canvas.winfo_height(), 600)
        stage_top = 58
        stage_bottom = height - 183
        centre_x = width / 2
        centre_y = (stage_top + stage_bottom) / 2
        self.view_offset_x = offset_after_zoom(
            self.view_offset_x, old_zoom, new_zoom, focal_x, centre_x
        )
        self.view_offset_y = offset_after_zoom(
            self.view_offset_y, old_zoom, new_zoom, focal_y, centre_y
        )
        self.zoom_factor = new_zoom
        if abs(new_zoom - 1.0) < 0.015:
            self.zoom_factor = 1.0
            self.view_offset_x = 0.0
            self.view_offset_y = 0.0
        self._clamp_view_offset()
        self.draw_scene()
        self.status_var.set(f"View zoom: {round(self.zoom_factor * 100)}%  ·  ⌘0 resets")

    def _clamp_view_offset(self) -> None:
        width = max(self.canvas.winfo_width(), 700)
        height = max(self.canvas.winfo_height(), 600)
        excess = max(0.0, self.zoom_factor - 1.0)
        limit_x = width * excess / 2 + 80
        limit_y = (height - 183) * excess / 2 + 60
        self.view_offset_x = max(-limit_x, min(limit_x, self.view_offset_x))
        self.view_offset_y = max(-limit_y, min(limit_y, self.view_offset_y))

    def _reset_view(self, _event=None) -> str:
        self.zoom_factor = 1.0
        self.view_offset_x = 0.0
        self.view_offset_y = 0.0
        self.draw_scene()
        self.set_status("View reset to 100%.")
        return "break"

    def _screen_to_layout(self, x: float, y: float) -> tuple[float, float]:
        width = max(self.canvas.winfo_width(), 700)
        height = max(self.canvas.winfo_height(), 600)
        stage_top = 58
        stage_bottom = height - 183
        centre_x = width / 2
        centre_y = (stage_top + stage_bottom) / 2
        base_x = centre_x + (x - centre_x - self.view_offset_x) / self.zoom_factor
        base_y = centre_y + (y - centre_y - self.view_offset_y) / self.zoom_factor
        return base_x, base_y

    # ---------- drawing ----------

    def draw_scene(self) -> None:
        self._redraw_job = None
        self.canvas.delete("scene")
        self.canvas.delete("temporary")
        self.seat_centres.clear()
        self.table_centres.clear()
        self.table_bounds.clear()

        width = max(self.canvas.winfo_width(), 700)
        height = max(self.canvas.winfo_height(), 600)
        roster_height = 168
        stage_top = 58
        stage_bottom = height - roster_height - 15

        self.canvas.create_rectangle(
            0,
            0,
            width,
            43,
            fill=COLOUR["canvas"],
            outline="",
            tags=("scene", "chrome"),
        )
        self.canvas.create_text(
            26,
            21,
            text="ROOM LAYOUT",
            anchor="w",
            fill=COLOUR["muted"],
            font=("Avenir Next", 10, "bold"),
            tags=("scene", "chrome"),
        )
        self.canvas.create_text(
            width - 26,
            21,
            text=(
                "Pinch to zoom  •  Two-finger scroll to pan  •  "
                f"Double-click table to rename  •  {round(self.zoom_factor * 100)}%"
            ),
            anchor="e",
            fill="#8993A2",
            font=("Avenir Next", 9),
            tags=("scene", "chrome"),
        )
        self.canvas.create_line(
            24, 42, width - 24, 42, fill="#DEDAD1", tags=("scene", "chrome")
        )

        base_scale = self._layout_scale(width, stage_bottom - stage_top)
        scale = base_scale * self.zoom_factor
        viewport_x = width / 2
        viewport_y = (stage_top + stage_bottom) / 2
        for table_id in range(self.plan.table_count):
            if table_id not in self.plan.table_positions:
                self.plan.table_positions[table_id] = (
                    0.5,
                    (table_id + 0.5) / self.plan.table_count,
                )
            nx, ny = self.plan.table_positions[table_id]
            base_x = 22 + nx * (width - 44)
            base_y = stage_top + ny * (stage_bottom - stage_top)
            cx = viewport_x + (base_x - viewport_x) * self.zoom_factor + self.view_offset_x
            cy = viewport_y + (base_y - viewport_y) * self.zoom_factor + self.view_offset_y
            self._draw_table(table_id, cx, cy, scale)

        self._draw_roster_zones(width, height)
        self.canvas.tag_raise("chrome")
        self._update_counts()

    def _layout_scale(self, width: float, stage_height: float) -> float:
        return max(0.66, min(1.0, (width - 90) / 790, stage_height / 528))

    def _draw_table(self, table_id: int, cx: float, cy: float, scale: float) -> None:
        self.table_centres[table_id] = (cx, cy)
        table_width = 790 * scale
        table_height = 46 * scale
        seat_size = 50 * scale
        seat_gap = 11 * scale
        table_tag = f"table:{table_id}"
        self.table_bounds[table_id] = (
            cx - table_width / 2,
            cy - table_height / 2,
            cx + table_width / 2,
            cy + table_height / 2,
        )

        self.canvas.create_rectangle(
            cx - table_width / 2 + 4,
            cy - table_height / 2 + 6,
            cx + table_width / 2 + 4,
            cy + table_height / 2 + 6,
            fill=COLOUR["shadow"],
            outline="",
            tags=("scene", table_tag, "tablecore"),
        )
        self.canvas.create_rectangle(
            cx - table_width / 2,
            cy - table_height / 2,
            cx + table_width / 2,
            cy + table_height / 2,
            fill=COLOUR["paper"],
            outline="#CCD2DB",
            width=2,
            tags=("scene", table_tag, "tablecore"),
        )
        table_seats = [seat for seat in self.plan.seats if seat.table == table_id]
        occupied = sum(seat.guest_id is not None for seat in table_seats)
        self.canvas.create_text(
            cx - 9 * scale,
            cy,
            text=self.plan.table_name(table_id).upper(),
            anchor="e",
            fill=COLOUR["ink"],
            font=("Avenir Next", max(7, round(10 * scale)), "bold"),
            tags=("scene", table_tag, "tablecore"),
        )
        self.canvas.create_text(
            cx + 9 * scale,
            cy,
            text=f"{occupied} / {len(table_seats)}",
            anchor="w",
            fill=COLOUR["muted"],
            font=("Avenir Next", max(7, round(9 * scale))),
            tags=("scene", table_tag, "tablecore"),
        )

        for seat in table_seats:
            # Positions follow the table clockwise: 0–11 left-to-right along
            # the top, then 12–23 right-to-left along the bottom.
            if seat.position < 12:
                column = seat.position
                side = -1
            else:
                column = 23 - seat.position
                side = 1
            margin = 28 * scale
            usable_width = table_width - 2 * margin
            sx = cx - table_width / 2 + margin + column * (usable_width / 11)
            sy = cy + side * (table_height / 2 + seat_gap + seat_size / 2)
            self.seat_centres[seat.id] = (sx, sy)
            self._draw_seat(seat.id, sx, sy, seat_size)

    def _draw_seat(self, seat_id: int, x: float, y: float, size: float) -> None:
        seat = self.plan.seats[seat_id]
        guest = self.plan.guest_for_seat(seat_id)
        half = size / 2
        tag = f"seat:{seat_id}"
        if guest:
            fill = COLOUR["female"] if guest.gender == "F" else COLOUR["male"]
            gender_outline = (
                COLOUR["female_line"] if guest.gender == "F" else COLOUR["male_line"]
            )
        else:
            fill = COLOUR["orange_soft"] if seat.locked else COLOUR["paper"]
            gender_outline = COLOUR["line"]
        outline = COLOUR["orange"] if seat.locked else gender_outline
        width = 3 if seat.locked else 1

        self.canvas.create_oval(
            x - half + 2,
            y - half + 3,
            x + half + 2,
            y + half + 3,
            fill=COLOUR["shadow"],
            outline="",
            tags=("scene", tag, "seat"),
        )
        self.canvas.create_oval(
            x - half,
            y - half,
            x + half,
            y + half,
            fill=fill,
            outline=outline,
            width=width,
            tags=("scene", tag, "seat"),
        )
        if guest:
            parts = guest.name.split(maxsplit=1)
            label = parts[0] if len(parts) == 1 else f"{parts[0]}\n{parts[1]}"
            self.canvas.create_text(
                x,
                y,
                text=label,
                width=max(40, size - 7),
                justify="center",
                fill=COLOUR["ink"],
                font=("Avenir Next", max(6, round(size / 7.2)), "bold"),
                tags=("scene", tag, "seat"),
            )
        else:
            self.canvas.create_text(
                x,
                y,
                text="EMPTY",
                fill="#A9AFB8",
                font=("Avenir Next", max(6, round(size / 7.5)), "bold"),
                tags=("scene", tag, "seat"),
            )
        if seat.locked:
            # Keep the icon comfortably inside the ring so it never merges
            # visually with the orange locked-seat outline.
            self._draw_padlock(x + half - 14, y - half + 15, 0.72, ("scene", tag, "seat"))

    def _draw_padlock(self, x: float, y: float, scale: float, tags) -> None:
        orange = COLOUR["orange"]
        self.canvas.create_arc(
            x - 5 * scale,
            y - 8 * scale,
            x + 5 * scale,
            y + 2 * scale,
            start=0,
            extent=180,
            style="arc",
            outline=orange,
            width=max(2, round(2 * scale)),
            tags=tags,
        )
        self.canvas.create_rectangle(
            x - 6 * scale,
            y - 2 * scale,
            x + 6 * scale,
            y + 7 * scale,
            fill=orange,
            outline=orange,
            tags=tags,
        )

    def _draw_roster_zones(self, width: float, height: float) -> None:
        top = height - 153
        gap = 12
        left = 24
        right = width - 24
        mid = (left + right) / 2
        self.bench_rect = (left, top, mid - gap / 2, height - 18)
        self.absent_rect = (mid + gap / 2, top, right, height - 18)
        self._draw_roster_zone("bench", self.bench_rect, self.plan.bench_guest_ids(), "BENCH")
        self._draw_roster_zone(
            "absent", self.absent_rect, self.plan.absent_guest_ids(), "NOT ATTENDING"
        )

    def _draw_roster_zone(
        self, kind: str, rect: tuple[float, float, float, float], guest_ids: list[str], title: str
    ) -> None:
        x1, y1, x2, y2 = rect
        is_bench = kind == "bench"
        fill = COLOUR["bench"] if is_bench else COLOUR["absent"]
        outline = COLOUR["bench_line"] if is_bench else "#D4D4D7"
        self.canvas.create_rectangle(
            x1, y1, x2, y2, fill=fill, outline=outline, width=1, tags="scene"
        )
        self.canvas.create_text(
            x1 + 14,
            y1 + 16,
            text=f"{title}  ·  {len(guest_ids)}",
            anchor="w",
            fill=COLOUR["ink"] if is_bench else COLOUR["absent_text"],
            font=("Avenir Next", 9, "bold"),
            tags="scene",
        )
        if not guest_ids:
            message = "Cleared guests wait here" if is_bench else "Everyone is coming"
            self.canvas.create_text(
                (x1 + x2) / 2,
                (y1 + y2) / 2 + 10,
                text=message,
                fill="#9AA1AB",
                font=("Avenir Next", 10),
                tags="scene",
            )
            return

        guest_ids = sorted(guest_ids, key=lambda item: self.plan.guests[item].name.lower())
        columns = max(2, int((x2 - x1 - 30) // 145))
        page_size = columns * 3
        current_page = self.bench_page if is_bench else self.absent_page
        max_page = max(0, math.ceil(len(guest_ids) / page_size) - 1)
        current_page = min(current_page, max_page)
        if is_bench:
            self.bench_page = current_page
        else:
            self.absent_page = current_page
        visible = guest_ids[current_page * page_size : (current_page + 1) * page_size]

        for index, guest_id in enumerate(visible):
            col = index % columns
            row = index // columns
            px = x1 + 14 + col * ((x2 - x1 - 28) / columns)
            py = y1 + 37 + row * 29
            pill_width = (x2 - x1 - 28) / columns - 7
            guest = self.plan.guests[guest_id]
            pill_tag = f"benchguest:{guest_id}" if is_bench else f"absentguest:{guest_id}"
            self.canvas.create_rectangle(
                px,
                py,
                px + pill_width,
                py + 23,
                fill=COLOUR["paper"] if is_bench else "#DDDEE1",
                outline="#C7CBD2" if is_bench else "#D0D1D4",
                tags=("scene", pill_tag, "benchguest" if is_bench else "absentguest"),
            )
            self.canvas.create_text(
                px + 8,
                py + 12,
                text=guest.name,
                width=pill_width - 16,
                anchor="w",
                fill=COLOUR["ink"] if is_bench else COLOUR["absent_text"],
                font=("Avenir Next", 8, "bold" if is_bench else "normal"),
                tags=("scene", pill_tag, "benchguest" if is_bench else "absentguest"),
            )

        if max_page:
            nav_x = x2 - 72
            nav_y = y1 + 16
            self.canvas.create_text(
                nav_x - 18,
                nav_y,
                text="‹",
                fill=COLOUR["ink"] if current_page else "#B6BAC1",
                font=("Avenir Next", 17, "bold"),
                tags=("scene", f"page:{kind}:prev", "pagecontrol"),
            )
            self.canvas.create_text(
                nav_x + 38,
                nav_y,
                text="›",
                fill=COLOUR["ink"] if current_page < max_page else "#B6BAC1",
                font=("Avenir Next", 17, "bold"),
                tags=("scene", f"page:{kind}:next", "pagecontrol"),
            )
            self.canvas.create_text(
                nav_x + 10,
                nav_y,
                text=f"{current_page + 1}/{max_page + 1}",
                fill=COLOUR["muted"],
                font=("Avenir Next", 8),
                tags="scene",
            )

    # ---------- interactions ----------

    def _current_tag(self, prefix: str) -> str | None:
        items = self.canvas.find_withtag("current")
        if not items:
            return None
        return next((tag for tag in self.canvas.gettags(items[-1]) if tag.startswith(prefix)), None)

    def _on_press(self, event) -> None:
        page_tag = self._current_tag("page:")
        if page_tag:
            _, kind, direction = page_tag.split(":")
            change = -1 if direction == "prev" else 1
            if kind == "bench":
                self.bench_page = max(0, self.bench_page + change)
            else:
                self.absent_page = max(0, self.absent_page + change)
            self.draw_scene()
            return

        bench_tag = self._current_tag("benchguest:")
        if bench_tag:
            self._start_guest_drag(bench_tag.split(":", 1)[1], event.x, event.y)
            return

        seat_tag = self._current_tag("seat:")
        if seat_tag:
            seat_id = int(seat_tag.split(":")[1])
            seat = self.plan.seats[seat_id]
            if seat.guest_id and not seat.locked:
                self._start_guest_drag(seat.guest_id, event.x, event.y)
            elif seat.locked:
                self.set_status("That seat is locked. Right-click it to unlock.")
            return

        table_tag = self._current_tag("table:")
        if table_tag:
            table_id = int(table_tag.split(":")[1])
            self.drag_table_id = table_id
            cx, cy = self.table_centres[table_id]
            self.drag_offset = (event.x - cx, event.y - cy)
            self.canvas.configure(cursor="fleur")

    def _start_guest_drag(self, guest_id: str, x: float, y: float) -> None:
        self.drag_guest_id = guest_id
        self.canvas.configure(cursor="hand2")
        self._draw_drag_badge(x, y)
        self.set_status(f"Moving {self.plan.guests[guest_id].name}…")

    def _draw_drag_badge(self, x: float, y: float) -> None:
        for item in self.drag_items:
            self.canvas.delete(item)
        self.drag_items.clear()
        guest = self.plan.guests[self.drag_guest_id] if self.drag_guest_id else None
        if not guest:
            return
        self.drag_items.extend(
            [
                self.canvas.create_oval(
                    x - 33,
                    y - 33,
                    x + 33,
                    y + 33,
                    fill="#D4D0C7",
                    outline="",
                    tags="temporary",
                ),
                self.canvas.create_oval(
                    x - 33,
                    y - 36,
                    x + 33,
                    y + 30,
                    fill=COLOUR["paper"],
                    outline=COLOUR["blue"],
                    width=3,
                    tags="temporary",
                ),
                self.canvas.create_text(
                    x,
                    y - 3,
                    text=guest.name,
                    width=58,
                    justify="center",
                    fill=COLOUR["ink"],
                    font=("Avenir Next", 8, "bold"),
                    tags="temporary",
                ),
            ]
        )

    def _on_motion(self, event) -> None:
        if self.drag_guest_id:
            self._draw_drag_badge(event.x, event.y)
            destination = self._nearest_seat(event.x, event.y)
            self.canvas.configure(cursor="hand2" if destination is not None else "exchange")
            return
        if self.drag_table_id is not None:
            width = max(self.canvas.winfo_width(), 1)
            height = max(self.canvas.winfo_height(), 1)
            roster_top = height - 168
            screen_x = event.x - self.drag_offset[0]
            screen_y = event.y - self.drag_offset[1]
            x, y = self._screen_to_layout(screen_x, screen_y)
            scale = self._layout_scale(width, roster_top - 58)
            table_half = 395 * scale
            vertical_half = 60 * scale
            x = min(width - table_half - 24, max(table_half + 24, x))
            y = min(roster_top - vertical_half - 15, max(58 + vertical_half + 8, y))
            self.plan.table_positions[self.drag_table_id] = (
                (x - 22) / max(1, width - 44),
                (y - 58) / max(1, roster_top - 73),
            )
            self.draw_scene()
            self.canvas.configure(cursor="fleur")

    def _on_release(self, event) -> None:
        if self.drag_table_id is not None:
            table_name = self.plan.table_name(self.drag_table_id)
            self.drag_table_id = None
            self.canvas.configure(cursor="arrow")
            self.set_status(f"{table_name} moved.")
            return
        if not self.drag_guest_id:
            return

        guest_id = self.drag_guest_id
        source = self.plan.seat_for_guest(guest_id)
        destination_id = self._nearest_seat(event.x, event.y)
        changed = False
        if destination_id is not None:
            changed = self.plan.move_guest(guest_id, destination_id)
            if changed:
                self.set_status(f"{self.plan.guests[guest_id].name} reseated.")
        elif self._point_in_rect(event.x, event.y, self.bench_rect):
            changed = self.plan.move_guest_to_bench(guest_id)
            if changed:
                self.set_status(f"{self.plan.guests[guest_id].name} moved to the bench.")

        self.drag_guest_id = None
        self.drag_items.clear()
        self.canvas.configure(cursor="arrow")
        self.draw_scene()
        if changed and destination_id is not None:
            self._pulse_seat(destination_id)
        elif not changed:
            self.set_status("No change — drop a guest onto an unlocked seat or the bench.")
            if source:
                self._pulse_seat(source.id, COLOUR["muted"])

    def _on_double_click(self, event) -> None:
        seat_id = self._seat_at_point(event.x, event.y)
        if seat_id is None:
            table_id = self._table_at_point(event.x, event.y)
            if table_id is not None:
                self.rename_table(table_id)
            return
        seat = self.plan.seats[seat_id]
        if seat.locked:
            self.set_status("Unlock that seat before clearing it.")
            self._pulse_seat(seat_id, COLOUR["orange"])
            return
        guest = self.plan.guest_for_seat(seat_id)
        if not guest:
            return
        start = self.seat_centres.get(seat_id)
        self.plan.clear_seat(seat_id)
        self.draw_scene()
        self.set_status(f"{guest.name} moved to the bench.")
        if start:
            target = ((self.bench_rect[0] + self.bench_rect[2]) / 2, self.bench_rect[1] + 55)
            self._animate_name_move(guest.name, start, target)

    def _table_at_point(self, x: float, y: float) -> int | None:
        for table_id, (x1, y1, x2, y2) in self.table_bounds.items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                return table_id
        return None

    def rename_table(self, table_id: int) -> None:
        current = self.plan.table_name(table_id)
        name = simpledialog.askstring(
            "Rename table",
            "Table name:",
            initialvalue=current,
            parent=self,
        )
        if name is None:
            return
        renamed = self.plan.rename_table(table_id, name)
        self.draw_scene()
        self.set_status(f"Table renamed to “{renamed}”.")

    def _on_right_click(self, event) -> None:
        seat_id = self._seat_at_point(event.x, event.y)
        if seat_id is None:
            return
        locked = self.plan.toggle_lock(seat_id)
        guest = self.plan.guest_for_seat(seat_id)
        self.draw_scene()
        self._animate_lock(seat_id, locked)
        who = guest.name if guest else f"Seat {seat_id + 1}"
        self.set_status(f"{who} {'locked' if locked else 'unlocked'}.")

    def _nearest_seat(self, x: float, y: float) -> int | None:
        candidates = sorted(
            ((math.hypot(x - sx, y - sy), seat_id) for seat_id, (sx, sy) in self.seat_centres.items()),
            key=lambda item: item[0],
        )
        if not candidates or candidates[0][0] > 38:
            return None
        seat_id = candidates[0][1]
        return None if self.plan.seats[seat_id].locked else seat_id

    def _seat_at_point(self, x: float, y: float) -> int | None:
        candidates = sorted(
            ((math.hypot(x - sx, y - sy), seat_id) for seat_id, (sx, sy) in self.seat_centres.items()),
            key=lambda item: item[0],
        )
        return candidates[0][1] if candidates and candidates[0][0] <= 38 else None

    @staticmethod
    def _point_in_rect(x: float, y: float, rect: tuple[float, float, float, float]) -> bool:
        x1, y1, x2, y2 = rect
        return x1 <= x <= x2 and y1 <= y <= y2

    # ---------- commands ----------

    def randomise(self) -> None:
        message = self.plan.randomize(rng=random.Random())
        self.draw_scene()
        self._animate_shuffle()
        self.set_status(message)

    def randomise_genders(self) -> None:
        message = self.plan.randomize(gender_alternating=True, rng=random.Random())
        self.draw_scene()
        self._animate_shuffle()
        self.set_status(message)

    def save_current(self) -> None:
        default = f"Plan {len(self.save_manager.list_saves()) + 1}"
        name = simpledialog.askstring("Save seating plan", "Name this plan:", initialvalue=default, parent=self)
        if not name:
            return
        try:
            path = self.save_manager.save(self.plan, name)
        except OSError as error:
            messagebox.showerror("Could not save", str(error), parent=self)
            return
        self.refresh_saves()
        self.set_status(f"Saved as “{path.stem}”.")
        self._flash_canvas(COLOUR["green"])

    def refresh_saves(self) -> None:
        for child in self.saves_list.winfo_children():
            child.destroy()
        paths = self.save_manager.list_saves()
        if not paths:
            tk.Label(
                self.saves_list,
                text="No saved plans yet.",
                bg=COLOUR["navy"],
                fg="#76869E",
                font=("Avenir Next", 9),
            ).pack(anchor="w", padx=8, pady=8)
            return
        for path in paths:
            button = tk.Label(
                self.saves_list,
                text=f"  {path.stem}\n  Click for options",
                justify="left",
                anchor="w",
                bg=COLOUR["navy_2"],
                fg="white",
                cursor="hand2",
                font=("Avenir Next", 9, "bold"),
                padx=8,
                pady=7,
            )
            button.pack(fill="x", padx=5, pady=4)
            button.bind(
                "<Button-1>", lambda _event, selected=path: self.open_save_options(selected)
            )
            button.bind("<Enter>", lambda _event, item=button: item.configure(bg="#2C4264"))
            button.bind("<Leave>", lambda _event, item=button: item.configure(bg=COLOUR["navy_2"]))

    def open_save_options(self, path: Path) -> None:
        dialog = tk.Toplevel(self)
        dialog.title(path.stem)
        dialog.geometry("360x230")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(bg=COLOUR["paper"])
        tk.Label(
            dialog,
            text=path.stem,
            bg=COLOUR["paper"],
            fg=COLOUR["ink"],
            font=("Avenir Next", 18, "bold"),
            wraplength=320,
        ).pack(pady=(22, 4))
        tk.Label(
            dialog,
            text="What would you like to do?",
            bg=COLOUR["paper"],
            fg=COLOUR["muted"],
            font=("Avenir Next", 10),
        ).pack(pady=(0, 16))
        row = tk.Frame(dialog, bg=COLOUR["paper"])
        row.pack()
        self._dialog_button(row, "Load", lambda: self._load_save(path, dialog), COLOUR["green"])
        self._dialog_button(row, "Rename", lambda: self._rename_save(path, dialog), COLOUR["blue"])
        self._dialog_button(row, "Delete", lambda: self._delete_save(path, dialog), COLOUR["danger"])

    def _dialog_button(self, parent, text: str, command, colour: str) -> None:
        button = tk.Label(
            parent,
            text=text,
            bg=colour,
            fg="white",
            cursor="hand2",
            font=("Avenir Next", 10, "bold"),
            padx=16,
            pady=9,
        )
        button.pack(side="left", padx=5)
        button.bind("<Button-1>", lambda _event: command())
        button.bind("<Enter>", lambda _event: button.configure(relief="raised"))
        button.bind("<Leave>", lambda _event: button.configure(relief="flat"))

    def _load_save(self, path: Path, dialog: tk.Toplevel) -> None:
        try:
            self.plan = self.save_manager.load(path)
        except (OSError, ValueError, KeyError, TypeError) as error:
            messagebox.showerror("Could not load", str(error), parent=dialog)
            return
        dialog.destroy()
        self.bench_page = self.absent_page = 0
        self.draw_scene()
        self._flash_canvas(COLOUR["blue"])
        self.set_status(f"Loaded “{path.stem}”.")

    def _rename_save(self, path: Path, dialog: tk.Toplevel) -> None:
        name = simpledialog.askstring("Rename plan", "New name:", initialvalue=path.stem, parent=dialog)
        if not name:
            return
        try:
            target = self.save_manager.rename(path, name)
        except OSError as error:
            messagebox.showerror("Could not rename", str(error), parent=dialog)
            return
        dialog.destroy()
        self.refresh_saves()
        self.set_status(f"Renamed plan to “{target.stem}”.")

    def _delete_save(self, path: Path, dialog: tk.Toplevel) -> None:
        confirmed = messagebox.askyesno(
            "Delete saved plan?",
            f"Delete “{path.stem}”?\n\nThis cannot be undone.",
            parent=dialog,
        )
        if not confirmed:
            return
        try:
            self.save_manager.delete(path)
        except OSError as error:
            messagebox.showerror("Could not delete", str(error), parent=dialog)
            return
        dialog.destroy()
        self.refresh_saves()
        self.set_status(f"Deleted saved plan “{path.stem}”.")

    def open_guest_editor(self) -> None:
        editor = tk.Toplevel(self)
        editor.title("Edit guests")
        editor.geometry("640x680")
        editor.minsize(520, 520)
        editor.transient(self)
        editor.grab_set()
        editor.configure(bg=COLOUR["paper"])

        tk.Label(
            editor,
            text="Guests",
            bg=COLOUR["paper"],
            fg=COLOUR["ink"],
            font=("Avenir Next", 22, "bold"),
        ).pack(anchor="w", padx=26, pady=(22, 2))
        tk.Label(
            editor,
            text=(
                "Untick anyone who is not coming. Choose M or F if a name was "
                "inferred incorrectly."
            ),
            bg=COLOUR["paper"],
            fg=COLOUR["muted"],
            font=("Avenir Next", 10),
            justify="left",
            wraplength=570,
        ).pack(anchor="w", padx=27, pady=(0, 14))

        attendance_variables: dict[str, tk.BooleanVar] = {}
        gender_variables: dict[str, tk.StringVar] = {}
        rows: dict[str, tk.Frame] = {}
        checks: dict[str, tk.Checkbutton] = {}
        gender_buttons: dict[str, tuple[tk.Radiobutton, tk.Radiobutton]] = {}

        def restyle(guest_id: str) -> None:
            active = attendance_variables[guest_id].get()
            background = "#F3F4F6" if active else "#E4E5E8"
            foreground = COLOUR["ink"] if active else COLOUR["absent_text"]
            rows[guest_id].configure(bg=background)
            checks[guest_id].configure(
                fg=foreground,
                bg=background,
                activebackground=background,
                selectcolor=background,
            )
            for button in gender_buttons[guest_id]:
                button.configure(
                    fg=foreground,
                    bg=background,
                    activebackground=background,
                )

        def set_all_attendance(attending: bool) -> None:
            for guest_id, variable in attendance_variables.items():
                variable.set(attending)
                restyle(guest_id)

        bulk_controls = tk.Frame(editor, bg=COLOUR["paper"])
        bulk_controls.pack(fill="x", padx=21, pady=(0, 10))
        self._dialog_button(
            bulk_controls,
            "Check all",
            lambda: set_all_attendance(True),
            COLOUR["green"],
        )
        self._dialog_button(
            bulk_controls,
            "Uncheck all",
            lambda: set_all_attendance(False),
            COLOUR["navy_2"],
        )

        list_shell = tk.Frame(editor, bg="#F3F4F6", highlightbackground=COLOUR["line"], highlightthickness=1)
        list_shell.pack(fill="both", expand=True, padx=26)
        guest_canvas = tk.Canvas(list_shell, bg="#F3F4F6", highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(list_shell, orient="vertical", command=guest_canvas.yview)
        inner = tk.Frame(guest_canvas, bg="#F3F4F6")
        window = guest_canvas.create_window((0, 0), window=inner, anchor="nw")
        guest_canvas.configure(yscrollcommand=scrollbar.set)
        guest_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        inner.bind("<Configure>", lambda _e: guest_canvas.configure(scrollregion=guest_canvas.bbox("all")))
        guest_canvas.bind("<Configure>", lambda e: guest_canvas.itemconfigure(window, width=e.width))

        for guest in sorted(self.plan.guests.values(), key=lambda item: (item.name.lower(), item.id)):
            attendance = tk.BooleanVar(value=guest.attending)
            gender = tk.StringVar(value=guest.gender)
            attendance_variables[guest.id] = attendance
            gender_variables[guest.id] = gender
            row = tk.Frame(inner, bg="#F3F4F6")
            row.pack(fill="x", padx=5, pady=1)
            check = tk.Checkbutton(
                row,
                text=guest.name,
                variable=attendance,
                command=lambda guest_id=guest.id: restyle(guest_id),
                anchor="w",
                bg="#F3F4F6",
                fg=COLOUR["ink"],
                activebackground="#E9ECF0",
                activeforeground=COLOUR["ink"],
                selectcolor="#F3F4F6",
                font=("Avenir Next", 10),
                padx=12,
                pady=6,
                bd=0,
            )
            check.pack(side="left", fill="x", expand=True)
            female = tk.Radiobutton(
                row,
                text="F",
                variable=gender,
                value="F",
                bg="#F3F4F6",
                fg=COLOUR["ink"],
                activebackground="#F3F4F6",
                selectcolor=COLOUR["female"],
                font=("Avenir Next", 10, "bold"),
                bd=0,
                padx=8,
            )
            male = tk.Radiobutton(
                row,
                text="M",
                variable=gender,
                value="M",
                bg="#F3F4F6",
                fg=COLOUR["ink"],
                activebackground="#F3F4F6",
                selectcolor=COLOUR["male"],
                font=("Avenir Next", 10, "bold"),
                bd=0,
                padx=8,
            )
            female.pack(side="right", padx=(0, 8))
            male.pack(side="right")
            rows[guest.id] = row
            checks[guest.id] = check
            gender_buttons[guest.id] = (male, female)
            restyle(guest.id)

        footer = tk.Frame(editor, bg=COLOUR["paper"])
        footer.pack(fill="x", padx=26, pady=18)

        def apply_changes() -> None:
            attendance_changes = 0
            gender_changes = 0
            for guest_id, variable in attendance_variables.items():
                if self.plan.guests[guest_id].attending != variable.get():
                    self.plan.set_attending(guest_id, variable.get())
                    attendance_changes += 1
                selected_gender = gender_variables[guest_id].get()
                if self.plan.guests[guest_id].gender != selected_gender:
                    self.plan.set_gender(guest_id, selected_gender)
                    gender_changes += 1
            editor.destroy()
            self.bench_page = self.absent_page = 0
            self.draw_scene()
            self._flash_canvas(COLOUR["blue"])
            total = attendance_changes + gender_changes
            if total:
                parts = []
                if attendance_changes:
                    parts.append(
                        f"{attendance_changes} attendance "
                        f"change{'s' if attendance_changes != 1 else ''}"
                    )
                if gender_changes:
                    parts.append(
                        f"{gender_changes} gender change{'s' if gender_changes != 1 else ''}"
                    )
                self.set_status(
                    f"Guest list updated — {' and '.join(parts)}."
                )
            else:
                self.set_status("Guest list unchanged.")

        cancel = tk.Label(
            footer,
            text="Cancel",
            bg="#E8EBEF",
            fg=COLOUR["ink"],
            cursor="hand2",
            font=("Avenir Next", 10, "bold"),
            padx=18,
            pady=9,
        )
        cancel.pack(side="right", padx=(8, 0))
        cancel.bind("<Button-1>", lambda _event: editor.destroy())
        apply_button = tk.Label(
            footer,
            text="Apply changes",
            bg=COLOUR["green"],
            fg="white",
            cursor="hand2",
            font=("Avenir Next", 10, "bold"),
            padx=18,
            pady=9,
        )
        apply_button.pack(side="right")
        apply_button.bind("<Button-1>", lambda _event: apply_changes())
        apply_button.bind("<Enter>", lambda _event: apply_button.configure(bg=COLOUR["green_hover"]))
        apply_button.bind("<Leave>", lambda _event: apply_button.configure(bg=COLOUR["green"]))

    # ---------- small animations and status ----------

    def _pulse_seat(self, seat_id: int, colour: str | None = None) -> None:
        centre = self.seat_centres.get(seat_id)
        if not centre:
            return
        x, y = centre
        colour = colour or COLOUR["green"]
        ring = self.canvas.create_oval(x - 31, y - 31, x + 31, y + 31, outline=colour, width=3, tags="temporary")

        def frame(step: int) -> None:
            if step >= 7 or not self.canvas.winfo_exists():
                self.canvas.delete(ring)
                return
            radius = 31 + step * 3
            self.canvas.coords(ring, x - radius, y - radius, x + radius, y + radius)
            self.canvas.itemconfigure(ring, width=max(1, 3 - step // 3))
            self.after(35, frame, step + 1)

        frame(0)

    def _animate_lock(self, seat_id: int, locked: bool) -> None:
        centre = self.seat_centres.get(seat_id)
        if not centre:
            return
        x, y = centre
        ring = self.canvas.create_oval(
            x - 25, y - 25, x + 25, y + 25, outline=COLOUR["orange"], width=4, tags="temporary"
        )

        def frame(step: int) -> None:
            if step >= 9:
                self.canvas.delete(ring)
                return
            bounce = math.sin(step / 8 * math.pi) * (11 if locked else 6)
            radius = 25 + bounce
            self.canvas.coords(ring, x - radius, y - radius, x + radius, y + radius)
            self.after(28, frame, step + 1)

        frame(0)

    def _animate_shuffle(self) -> None:
        for index, (cx, cy) in enumerate(self.table_centres.values()):
            def pulse(x=cx, y=cy):
                ring = self.canvas.create_oval(
                    x - 55, y - 55, x + 55, y + 55, outline=COLOUR["green"], width=3, tags="temporary"
                )
                self.after(190, lambda item=ring: self.canvas.delete(item))

            self.after(index * 45, pulse)

    def _animate_name_move(
        self, name: str, start: tuple[float, float], target: tuple[float, float]
    ) -> None:
        x, y = start
        badge = self.canvas.create_text(
            x,
            y,
            text=name,
            fill=COLOUR["blue"],
            font=("Avenir Next", 9, "bold"),
            tags="temporary",
        )

        def frame(step: int) -> None:
            if step > 10:
                self.canvas.delete(badge)
                return
            progress = step / 10
            eased = 1 - (1 - progress) ** 3
            bx = start[0] + (target[0] - start[0]) * eased
            by = start[1] + (target[1] - start[1]) * eased - math.sin(progress * math.pi) * 22
            self.canvas.coords(badge, bx, by)
            self.after(24, frame, step + 1)

        frame(0)

    def _flash_canvas(self, colour: str) -> None:
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        veil = self.canvas.create_rectangle(
            0, 0, width, height, fill=colour, stipple="gray75", outline="", tags="temporary"
        )
        self.after(115, lambda: self.canvas.delete(veil))

    def _update_counts(self) -> None:
        attending = len(self.plan.attending_guest_ids())
        seated = sum(seat.guest_id is not None for seat in self.plan.seats)
        locked = sum(seat.locked for seat in self.plan.seats)
        self.count_var.set(f"{seated} seated  ·  {attending} coming  ·  {locked} locked")

    def set_status(self, message: str) -> None:
        self.status_var.set(message)
        if self._status_job:
            self.after_cancel(self._status_job)
        self._status_job = self.after(
            6000, lambda: self.status_var.set("Drag names between seats. Right-click to lock.")
        )


def find_guest_file(explicit: str | None = None) -> Path:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Guest file not found: {path}")
        return path
    preferred = APP_DIR / "guests.txt"
    if preferred.exists():
        return preferred
    candidates = sorted(APP_DIR.glob("*.txt"))
    if candidates:
        return candidates[0]
    raise FileNotFoundError(
        "No guest list was found. Put guests.txt beside party_seat_planner.py, with one name per line."
    )


def create_app(guest_file: Path, enable_native_pinch: bool = True) -> PartySeatPlanner:
    names = read_guest_names(guest_file)
    return PartySeatPlanner(
        SeatingPlan.from_names(names),
        guest_file,
        enable_native_pinch=enable_native_pinch,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Visually arrange guests around party tables.")
    parser.add_argument("--guests", help="Optional path to a one-name-per-line text file.")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Open briefly, build the full interface, then exit automatically.",
    )
    parser.add_argument(
        "--no-native-pinch",
        action="store_true",
        help="Disable the native trackpad bridge; keyboard and Command+scroll zoom remain.",
    )
    args = parser.parse_args()
    compatibility_issue = runtime_compatibility_issue()
    if compatibility_issue:
        print(f"Party Seat Planner: {compatibility_issue}")
        raise SystemExit(1)
    try:
        guest_file = find_guest_file(args.guests)
        app = create_app(guest_file, enable_native_pinch=not args.no_native_pinch)
    except (OSError, ValueError) as error:
        print(f"Party Seat Planner: {error}")
        raise SystemExit(1) from error
    if args.smoke_test:
        app._smoke_failed = False

        def exercise_native_bridge() -> None:
            bridge = app._pinch_bridge
            if not bridge or not bridge.available:
                detail = bridge.error if bridge else "bridge did not initialise"
                print(f"Native pinch smoke test failed: {detail}")
                app._smoke_failed = True
                app.after(50, verify_native_bridge)
                return
            if not bridge.emit_test_pinch(0.12):
                print("Native pinch smoke test failed: event was not queued")
                app._smoke_failed = True
            app.after(350, verify_native_bridge)

        def verify_native_bridge() -> None:
            if app.zoom_factor <= 1.05:
                print("Native pinch smoke test failed: zoom callback was not delivered")
                app._smoke_failed = True
            elif not app._smoke_failed:
                print(f"Native pinch smoke test passed at {round(app.zoom_factor * 100)}% zoom")
            app.destroy()

        app.after(300, exercise_native_bridge)
    app.mainloop()
    if args.smoke_test and app._smoke_failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
