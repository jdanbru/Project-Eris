"""
gui/theme.py
────────────
Project Eris – design tokens and colour palette.

All colours used across the application are defined here so changes only
need to be made in one place.  The palette is intentionally kept close to
the original HTML mockup that was approved before coding began.

Colour ramps follow the mockup naming convention:
  BLUE_*   – primary accent colour (buttons, badges, active states)
  GREEN_*  – success / logging active
  RED_*    – error / stop action / danger
  AMBER_*  – warning / retrying state
  TEAL_*   – Siemens S7 badge colour
  GRAY_*   – neutral / disconnected

CustomTkinter supports (light_value, dark_value) tuples for any colour
argument, so helpers like card_bg() and surface_bg() return tuples that
automatically adapt when the user switches themes.
"""

# Project Eris – design tokens matching the HTML mockup aesthetic

BLUE_PRIMARY   = "#185FA5"
BLUE_LIGHT     = "#E6F1FB"
BLUE_BORDER    = "#B5D4F4"
BLUE_HOVER     = "#0C447C"

GREEN_PRIMARY  = "#3B6D11"
GREEN_LIGHT    = "#EAF3DE"
GREEN_BORDER   = "#C0DD97"

RED_PRIMARY    = "#A32D2D"
RED_LIGHT      = "#FCEBEB"

AMBER_PRIMARY  = "#854F0B"
AMBER_LIGHT    = "#FAEEDA"

TEAL_PRIMARY   = "#0F6E56"
TEAL_LIGHT     = "#E1F5EE"
TEAL_BORDER    = "#9FE1CB"

GRAY_MID       = "#888780"
GRAY_LIGHT     = "#F1EFE8"

STATUS_COLORS = {
    "connected":    GREEN_PRIMARY,
    "disconnected": GRAY_MID,
    "error":        RED_PRIMARY,
    "retrying":     AMBER_PRIMARY,
}

BADGE_AB = {"fg": BLUE_PRIMARY,  "bg": BLUE_LIGHT,  "border": BLUE_BORDER}
BADGE_S7 = {"fg": TEAL_PRIMARY,  "bg": TEAL_LIGHT,  "border": TEAL_BORDER}


def badge_colors(plc_type):
    return BADGE_AB if plc_type == "ab" else BADGE_S7


# ── CustomTkinter appearance helpers ──────────────────────────────────────

def sidebar_bg(mode):
    return "gray95" if mode == "light" else "gray14"

def card_bg(mode):
    return ("white", "gray17")

def topbar_bg(mode):
    return ("white", "gray17")

def surface_bg(mode):
    return ("gray92", "gray22")

def border_color(mode):
    return ("gray85", "gray30")

def text_secondary():
    return ("gray40", "gray65")

def text_muted():
    return ("gray60", "gray50")
