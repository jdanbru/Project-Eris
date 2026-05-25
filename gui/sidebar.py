"""
gui/sidebar.py
──────────────
Project Eris – left-hand sidebar.

Contains:
  - Company logo (loaded from assets/logo.png)
  - "JD Controls, LLC" company name (top)
  - "Project Eris" product name (below company name)
  - Navigation buttons for each screen
  - Scrollable list of PLC connection cards showing live status
  - "Add connection" button
  - Footer showing how many connections are active

The Sidebar does not manage any state itself — it receives all data
through update_connections() and calls the on_* callbacks when the user
interacts with it.  This keeps the sidebar purely presentational.
"""

import customtkinter as ctk
from PIL import Image
from pathlib import Path
from plc import STATUS_CONNECTED, STATUS_ERROR, STATUS_RETRYING
from gui.theme import STATUS_COLORS, badge_colors, BLUE_PRIMARY, BLUE_LIGHT

# Navigation items: (screen_key, display_label)
# The order here is the order they appear in the sidebar.
NAV_ITEMS = [
    ("dashboard",   "Dashboard"),
    ("data_viewer", "Data Viewer"),
    ("connections", "Connections"),
    ("csv",         "CSV Logs"),
    ("diagnostics", "Diagnostics"),
    ("help",        "Help"),
    ("settings",    "Settings"),
]

# Absolute path to the logo image, relative to this file's location
LOGO_PATH = Path(__file__).parent.parent / "assets" / "logo.png"


class Sidebar(ctk.CTkFrame):
    """
    Left-hand navigation sidebar.

    Parameters passed in at construction:
        on_nav(screen_key)       – called when the user clicks a nav button
        on_conn_select(conn_id)  – called when the user clicks a connection card
        on_add_conn()            – called when the user clicks "+ Add connection"
    """

    def __init__(self, parent, on_nav, on_conn_select, on_add_conn):
        super().__init__(parent, width=220, corner_radius=0,
                         fg_color=("gray95", "gray14"), border_width=0)
        self.on_nav          = on_nav
        self.on_conn_select  = on_conn_select
        self.on_add_conn     = on_add_conn
        self._nav_btns       = {}   # { screen_key: CTkButton }
        self._active         = None  # currently highlighted nav key
        self.grid_propagate(False)   # keep the sidebar at its fixed width
        self._build()

    def _build(self):
        """Construct all sidebar widgets."""
        # Row 4 (connection scroll area) gets all the vertical growth
        self.grid_rowconfigure(4, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── header: logo + company name + product name + theme toggle ─────
        hdr = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)

        # Logo image — loaded from assets/logo.png.
        # Silently skipped if the file is missing so the app still starts.
        try:
            img = ctk.CTkImage(
                light_image=Image.open(LOGO_PATH),
                dark_image=Image.open(LOGO_PATH),
                size=(36, 24),
            )
            ctk.CTkLabel(hdr, image=img, text="").grid(
                row=0, column=0, padx=(14, 6), pady=(14, 0), sticky="w")
        except Exception:
            pass   # logo not found — continue without it

        # Title row: company name on the left, theme toggle on the right
        title_row = ctk.CTkFrame(hdr, fg_color="transparent")
        title_row.grid(row=1, column=0, sticky="ew", padx=12, pady=(6, 0))
        title_row.grid_columnconfigure(0, weight=1)

        # ── "JD Controls, LLC" — company name, top line ───────────────────
        ctk.CTkLabel(title_row,
                     text="JD Controls, LLC",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     anchor="w").grid(row=0, column=0, sticky="w")


        # ── "Project Eris" — product name, second line ────────────────────
        ctk.CTkLabel(hdr,
                     text="  Project Eris  v4.3",
                     font=ctk.CTkFont(size=10),
                     text_color=("gray55", "gray55"),
                     anchor="w").grid(row=2, column=0, sticky="w", padx=12, pady=(0, 10))

        # sep
        ctk.CTkFrame(self, height=1, fg_color=("gray80", "gray30"),
                     corner_radius=0).grid(row=1, column=0, sticky="ew")

        # ── nav ───────────────────────────────────────────────────────────
        nav = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        nav.grid(row=2, column=0, sticky="ew", pady=(8, 0))

        ctk.CTkLabel(nav, text="  VIEWS",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=("gray55", "gray55"),
                     anchor="w").pack(fill="x", padx=10, pady=(2, 2))

        for key, label in NAV_ITEMS:
            btn = ctk.CTkButton(
                nav,
                text=label,
                anchor="w",
                fg_color="transparent",
                text_color=("gray20", "gray85"),
                hover_color=("gray85", "gray26"),
                corner_radius=6,
                height=32,
                font=ctk.CTkFont(size=13),
                command=lambda k=key: self.on_nav(k),
            )
            btn.pack(fill="x", padx=8, pady=1)
            self._nav_btns[key] = btn

        # sep
        ctk.CTkFrame(self, height=1, fg_color=("gray80", "gray30"),
                     corner_radius=0).grid(row=3, column=0, sticky="ew", pady=(8, 0))

        # ── connections ───────────────────────────────────────────────────
        conn_section = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        conn_section.grid(row=4, column=0, sticky="nsew", pady=(8, 0))
        conn_section.grid_rowconfigure(1, weight=1)
        conn_section.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(conn_section, text="  CONNECTIONS",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=("gray55", "gray55"),
                     anchor="w").grid(row=0, column=0, sticky="ew", padx=10, pady=(0, 4))

        self._conn_scroll = ctk.CTkScrollableFrame(
            conn_section, fg_color="transparent", corner_radius=0)
        self._conn_scroll.grid(row=1, column=0, sticky="nsew")
        self._conn_scroll.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            conn_section,
            text="+ Add connection",
            anchor="w",
            fg_color="transparent",
            text_color=("gray50", "gray50"),
            hover_color=("gray85", "gray26"),
            border_width=1,
            border_color=("gray70", "gray40"),
            corner_radius=6,
            height=28,
            font=ctk.CTkFont(size=12),
            command=self.on_add_conn,
        ).grid(row=2, column=0, sticky="ew", padx=8, pady=6)

        # ── footer ────────────────────────────────────────────────────────
        self._footer = ctk.CTkLabel(
            self, text="  0 of 0 connected",
            font=ctk.CTkFont(size=11),
            text_color=("gray55", "gray55"),
            anchor="w",
        )
        self._footer.grid(row=5, column=0, sticky="ew", padx=4, pady=8)

    def set_active(self, key):
        self._active = key
        for k, btn in self._nav_btns.items():
            if k == key:
                btn.configure(
                    fg_color=("gray82", "gray28"),
                    font=ctk.CTkFont(size=13, weight="bold"),
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    font=ctk.CTkFont(size=13),
                )

    def update_connections(self, conns):
        for w in self._conn_scroll.winfo_children():
            w.destroy()

        connected = sum(1 for c in conns if c["status"] == STATUS_CONNECTED)
        self._footer.configure(text=f"  {connected} of {len(conns)} connected")

        for item in conns:
            cfg    = item["cfg"]
            status = item["status"]
            color  = STATUS_COLORS.get(status, "#888780")
            bc     = badge_colors(cfg.get("plc_type", "ab"))
            is_active = item.get("active", False)

            card = ctk.CTkFrame(
                self._conn_scroll,
                fg_color=BLUE_LIGHT if is_active else ("white", "gray20"),
                corner_radius=6,
                border_width=1,
                border_color="#378ADD" if is_active else ("gray82", "gray35"),
            )
            card.grid(sticky="ew", padx=6, pady=3)
            card.grid_columnconfigure(0, weight=1)

            top = ctk.CTkFrame(card, fg_color="transparent")
            top.grid(row=0, column=0, sticky="ew", padx=8, pady=(6, 1))
            top.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(top,
                         text=cfg["name"],
                         font=ctk.CTkFont(size=12, weight="bold"),
                         anchor="w",
                         text_color="#0C447C" if is_active else ("gray10", "gray90"),
                         ).grid(row=0, column=0, sticky="w")

            ctk.CTkLabel(top,
                         text="AB" if cfg.get("plc_type") == "ab" else "S7",
                         font=ctk.CTkFont(size=10, weight="bold"),
                         text_color=bc["fg"],
                         fg_color=bc["bg"],
                         corner_radius=4,
                         width=26, height=16,
                         ).grid(row=0, column=1, sticky="e")

            ctk.CTkLabel(card,
                         text=cfg.get("ip", ""),
                         font=ctk.CTkFont(size=11),
                         text_color=("gray50", "gray55"),
                         anchor="w",
                         ).grid(row=1, column=0, sticky="w", padx=8)

            ctk.CTkLabel(card,
                         text=f"  ● {status.capitalize()}",
                         font=ctk.CTkFont(size=11),
                         text_color=color,
                         anchor="w",
                         ).grid(row=2, column=0, sticky="w", padx=8, pady=(0, 6))

            cid = cfg["id"]
            for w in [card] + list(card.winfo_children()):
                w.bind("<Button-1>", lambda e, c=cid: self.on_conn_select(c))
                for child in w.winfo_children():
                    child.bind("<Button-1>", lambda e, c=cid: self.on_conn_select(c))
