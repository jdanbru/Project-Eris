"""
gui/widgets.py
──────────────
Project Eris – reusable widget library.

Contains small, composable UI components that are shared across multiple
screens.  Using these keeps the screen files shorter and ensures a
consistent look everywhere without duplicating widget configuration.

Components:
  Card        – white bordered panel (the main container for content sections)
  StatTile    – metric display tile (label + large number, used in the stats row)
  PLCBadge    – small coloured "AB" or "S7" label
  StatusDot   – coloured status text ("● Connected")
  PrimaryBtn  – solid blue button (main actions like Save, Connect)
  GhostBtn    – outline-only button (secondary actions)
  DangerBtn   – red button (destructive actions like Delete, Stop)
  SuccessBtn  – green button (Start logging)
  LogPill     – small status indicator in the topbar ("● Logging" / "● Idle")
  panel_header – helper that returns a header row with title and optional right widget
  hsep        – horizontal separator line
  form_field  – helper that places a label + widget pair on a grid
"""

import customtkinter as ctk
from gui.theme import (
    BLUE_PRIMARY, BLUE_HOVER, BLUE_LIGHT,
    GREEN_PRIMARY, GREEN_LIGHT,
    RED_PRIMARY, RED_LIGHT,
    AMBER_PRIMARY,
    STATUS_COLORS, badge_colors,
    card_bg, surface_bg, border_color, text_secondary, text_muted,
)


# ── card frame ────────────────────────────────────────────────────────────
class Card(ctk.CTkFrame):
    def __init__(self, parent, **kw):
        super().__init__(
            parent,
            fg_color=card_bg(None),
            corner_radius=8,
            border_width=1,
            border_color=border_color(None),
            **kw,
        )


# ── section label ("VIEWS", "CONNECTIONS") ───────────────────────────────
class SectionLabel(ctk.CTkLabel):
    def __init__(self, parent, text, **kw):
        super().__init__(
            parent,
            text=text,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=text_muted(),
            anchor="w",
            **kw,
        )


# ── stat tile  ────────────────────────────────────────────────────────────
class StatTile(ctk.CTkFrame):
    def __init__(self, parent, label, value="—", value_color=None, **kw):
        super().__init__(
            parent,
            fg_color=surface_bg(None),
            corner_radius=6,
            **kw,
        )
        ctk.CTkLabel(
            self,
            text=label,
            font=ctk.CTkFont(size=11),
            text_color=text_muted(),
            anchor="w",
        ).pack(padx=10, pady=(8, 0), anchor="w")
        self._val = ctk.CTkLabel(
            self,
            text=value,
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=value_color or ("gray10", "gray90"),
            anchor="w",
        )
        self._val.pack(padx=10, pady=(0, 8), anchor="w")

    def set(self, value, color=None):
        self._val.configure(text=str(value))
        if color:
            self._val.configure(text_color=color)


# ── inline PLC type badge ────────────────────────────────────────────────
class PLCBadge(ctk.CTkLabel):
    def __init__(self, parent, plc_type, **kw):
        c = badge_colors(plc_type)
        super().__init__(
            parent,
            text="AB" if plc_type == "ab" else "S7",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=c["fg"],
            fg_color=c["bg"],
            corner_radius=4,
            width=26,
            height=18,
            **kw,
        )


# ── status dot label ─────────────────────────────────────────────────────
class StatusDot(ctk.CTkLabel):
    def __init__(self, parent, status="disconnected", **kw):
        color = STATUS_COLORS.get(status, "#888780")
        super().__init__(
            parent,
            text=f"  {status.capitalize()}",
            font=ctk.CTkFont(size=11),
            text_color=color,
            anchor="w",
            **kw,
        )

    def update_status(self, status):
        color = STATUS_COLORS.get(status, "#888780")
        self.configure(text=f"  {status.capitalize()}", text_color=color)


# ── primary button (blue) ────────────────────────────────────────────────
class PrimaryBtn(ctk.CTkButton):
    def __init__(self, parent, **kw):
        kw.setdefault("fg_color", BLUE_PRIMARY)
        kw.setdefault("hover_color", BLUE_HOVER)
        kw.setdefault("font", ctk.CTkFont(size=12))
        kw.setdefault("height", 30)
        super().__init__(parent, **kw)


# ── ghost button (outline only) ───────────────────────────────────────────
class GhostBtn(ctk.CTkButton):
    def __init__(self, parent, **kw):
        kw.setdefault("fg_color", "transparent")
        kw.setdefault("border_width", 1)
        kw.setdefault("border_color", border_color(None))
        kw.setdefault("text_color", text_secondary())
        kw.setdefault("hover_color", surface_bg(None))
        kw.setdefault("font", ctk.CTkFont(size=12))
        kw.setdefault("height", 30)
        super().__init__(parent, **kw)


# ── danger button ─────────────────────────────────────────────────────────
class DangerBtn(ctk.CTkButton):
    def __init__(self, parent, **kw):
        kw.setdefault("fg_color", RED_PRIMARY)
        kw.setdefault("hover_color", "#791F1F")
        kw.setdefault("text_color", RED_LIGHT)
        kw.setdefault("font", ctk.CTkFont(size=12))
        kw.setdefault("height", 30)
        super().__init__(parent, **kw)


# ── success button ────────────────────────────────────────────────────────
class SuccessBtn(ctk.CTkButton):
    def __init__(self, parent, **kw):
        kw.setdefault("fg_color", GREEN_PRIMARY)
        kw.setdefault("hover_color", "#27500A")
        kw.setdefault("text_color", GREEN_LIGHT)
        kw.setdefault("font", ctk.CTkFont(size=12))
        kw.setdefault("height", 30)
        super().__init__(parent, **kw)


# ── log-status pill ───────────────────────────────────────────────────────
class LogPill(ctk.CTkLabel):
    def __init__(self, parent, **kw):
        super().__init__(
            parent,
            text="● Idle",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60"),
            **kw,
        )

    def set_logging(self, logging: bool):
        if logging:
            self.configure(text="● Logging", text_color=GREEN_PRIMARY)
        else:
            self.configure(text="● Idle", text_color=("gray50", "gray60"))


# ── panel header row ──────────────────────────────────────────────────────
def panel_header(parent, title, right_widget=None):
    """Returns a frame with title on left, optional widget on right."""
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(
        row,
        text=title,
        font=ctk.CTkFont(size=13, weight="bold"),
        anchor="w",
    ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 6))
    if right_widget:
        right_widget.grid(row=0, column=1, sticky="e", padx=12, pady=(10, 6))
    return row


# ── horizontal separator ─────────────────────────────────────────────────
def hsep(parent):
    return ctk.CTkFrame(parent, height=1, fg_color=border_color(None), corner_radius=0)


# ── form field helper ─────────────────────────────────────────────────────
def form_field(parent, label, row, col, widget_factory, colspan=1):
    ctk.CTkLabel(
        parent,
        text=label,
        font=ctk.CTkFont(size=11),
        text_color=text_muted(),
        anchor="w",
    ).grid(row=row, column=col, columnspan=colspan, sticky="w", padx=12, pady=(8, 0))
    w = widget_factory(parent)
    w.grid(row=row + 1, column=col, columnspan=colspan, sticky="ew", padx=12, pady=(2, 4))
    return w
