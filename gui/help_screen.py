"""
gui/help_screen.py
──────────────────
Project Eris – Help screen.

A static reference page containing:
  - A numbered step-by-step guide for configuring a PLC connection
    (covers PLC type selection, IP/slot/rack entry, logging mode,
    tag addressing for both AB and Siemens, testing, and saving)
  - A troubleshooting tips section with PLC-specific advice:
      - Network configuration
      - Allen-Bradley slot numbering
      - Siemens PUT/GET enable in TIA Portal
      - S7-300 vs S7-1200/1500 differences
      - Data type sizing reference

All content is hard-coded here as Python strings rather than loaded from
a file, so the help page is always available even if the app is run from
a bare directory with no additional assets.
"""

import customtkinter as ctk
from gui.widgets import Card
from gui.theme import BLUE_PRIMARY, BLUE_LIGHT, GREEN_PRIMARY, text_muted

STEPS = [
    {
        "title": "Step 1 — Open the Connections screen",
        "body": (
            "Click Connections in the left sidebar, then click '+ Add connection' "
            "at the bottom of the sidebar to create a new connection slot."
        ),
    },
    {
        "title": "Step 2 — Choose your PLC type",
        "body": (
            "Select Allen-Bradley (pylogix) for ControlLogix, CompactLogix, or Micro8xx PLCs "
            "programmed with RSLogix 5000 / Studio 5000.\n\n"
            "Select Siemens S7 (snap7) for S7-300, S7-400, S7-1200, or S7-1500 PLCs.\n\n"
            "Note: PLC5, SLC, and MicroLogix are NOT supported by pylogix. "
            "For Siemens, ensure 'PUT/GET communication' is enabled in TIA Portal under "
            "Protection & Security settings."
        ),
    },
    {
        "title": "Step 3 — Enter connection details",
        "body": (
            "IP address: The IP address of your PLC (e.g. 192.168.1.10). "
            "Make sure the PC running Project Eris is on the same network subnet.\n\n"
            "Slot (Allen-Bradley): The processor slot in the chassis. Usually 0 for CompactLogix. "
            "ControlLogix may use a different slot — check your hardware configuration.\n\n"
            "Slot + Rack (Siemens): Usually Rack=0, Slot=1 for S7-300/400. "
            "For S7-1200/1500, use Rack=0, Slot=1."
        ),
    },
    {
        "title": "Step 4 — Choose logging mode",
        "body": (
            "Interval logging: Records tag values at a fixed time interval. "
            f"Minimum interval is 100ms. Typical values: 500ms, 1000ms, 5000ms.\n\n"
            "Trigger logging: Records one row each time a BOOL tag transitions from False → True "
            "(rising edge). Enter the tag name or DB address of your trigger tag. "
            "The program polls the trigger at 50ms so it won't miss fast triggers."
        ),
    },
    {
        "title": "Step 5 — Add tags to log",
        "body": (
            "Click '+ Add tag' and enter the tag address:\n\n"
            "Allen-Bradley: Use the tag name as it appears in Studio 5000 "
            "(e.g. Motor_Speed, Conveyor.Running, Tank[0].Level). "
            "UDT members use dot notation.\n\n"
            "Siemens S7: Enter the DB number and byte offset "
            "(e.g. DB1, offset 0 for the first value in DB1). "
            "Select the correct data type (REAL=4 bytes, INT=2 bytes, BOOL=1 byte, etc.).\n\n"
            "Use the Log? checkbox to enable or disable individual tags without deleting them."
        ),
    },
    {
        "title": "Step 6 — Test and save",
        "body": (
            "Click 'Test connection' to verify the program can reach the PLC. "
            "A success message means the connection works. If it fails:\n"
            "  • Check the IP address and subnet\n"
            "  • Check that the PLC is powered on and the Ethernet port is active\n"
            "  • For Siemens: verify PUT/GET is enabled in TIA Portal\n"
            "  • For Allen-Bradley: check the slot number\n\n"
            "Once the test passes, click Save to store the connection."
        ),
    },
    {
        "title": "Step 7 — Start logging",
        "body": (
            "Go to the Dashboard. Your connection should appear in the sidebar. "
            "Click '▶ Start logging' to begin writing data to CSV.\n\n"
            "CSV files are saved to the folder configured in Settings "
            "(default: your user folder → ProjectEris → Logs).\n\n"
            "Each time you click Start logging, a new file is created with a timestamp in its name. "
            "If a connection has 'Separate CSV' enabled, it gets its own subfolder."
        ),
    },
]

TIPS = [
    ("Network tips",
     "Ensure the PC and PLC are on the same subnet (e.g. 192.168.1.x with /24 mask). "
     "Disable Windows Firewall or add an exception for Project Eris if connection tests fail. "
     "For PLCs behind a router, routing must be configured — pylogix and snap7 are not VPN-aware."),

    ("Allen-Bradley tips",
     "For ControlLogix in a chassis, the processor slot may not be 0. "
     "Open RSLogix or Studio 5000, go to I/O Configuration to find the correct slot. "
     "If you get 'Forward Open failed', try a different slot number."),

    ("Siemens S7-1200/1500 tips",
     "In TIA Portal: open your PLC properties → Protection & Security → "
     "Connection mechanisms → enable 'Permit access with PUT/GET communication'. "
     "Without this, all connections will fail. Also set the IP address in the "
     "PROFINET interface properties."),

    ("Siemens S7-300/400 tips",
     "For S7-300, the slot is typically 2 (not 1). If connection fails, try Rack=0 Slot=2. "
     "The Diagnostics page has a 'Get full CPU info' button — avoid using this on S7-300 "
     "as it can cause a CPU fault on some firmware versions."),

    ("Data types",
     "Allen-Bradley: REAL=32-bit float, INT=16-bit integer, DINT=32-bit integer, BOOL=boolean. "
     "Siemens: REAL=4 bytes at offset, INT=2 bytes, DINT=4 bytes, BOOL=1 byte (byte only, bit addressing not supported). "
     "Mismatch between selected type and actual PLC type will cause incorrect readings."),
]


class HelpScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self._build()

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        tb = ctk.CTkFrame(self, corner_radius=0,
                          fg_color=("white", "gray17"),
                          border_width=1, border_color=("gray85", "gray30"))
        tb.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(tb, text="Help — Configuring a connection",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, padx=14, pady=10, sticky="w")

        scroll = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color="transparent")
        scroll.grid(row=1, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        r = 0

        # ── step-by-step guide ────────────────────────────────────────────
        ctk.CTkLabel(scroll, text="Connection setup guide",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=BLUE_PRIMARY,
                     anchor="w").grid(row=r, column=0, sticky="w", padx=14, pady=(12, 4))
        r += 1

        for i, step in enumerate(STEPS):
            card = Card(scroll)
            card.grid(row=r, column=0, sticky="ew", padx=12, pady=4)
            card.grid_columnconfigure(1, weight=1)

            # step number bubble
            bubble = ctk.CTkLabel(card,
                                   text=str(i + 1),
                                   font=ctk.CTkFont(size=12, weight="bold"),
                                   text_color="white",
                                   fg_color=BLUE_PRIMARY,
                                   corner_radius=14,
                                   width=28, height=28)
            bubble.grid(row=0, column=0, padx=(12, 8), pady=(10, 0), sticky="nw")

            ctk.CTkLabel(card, text=step["title"],
                         font=ctk.CTkFont(size=13, weight="bold"),
                         anchor="w").grid(row=0, column=1, sticky="w", padx=(0, 12), pady=(10, 2))

            ctk.CTkLabel(card, text=step["body"],
                         font=ctk.CTkFont(size=12),
                         anchor="w", justify="left",
                         wraplength=580).grid(row=1, column=0, columnspan=2,
                                              sticky="w", padx=12, pady=(0, 12))
            r += 1

        # ── tips ──────────────────────────────────────────────────────────
        ctk.CTkLabel(scroll, text="Tips & troubleshooting",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=BLUE_PRIMARY,
                     anchor="w").grid(row=r, column=0, sticky="w", padx=14, pady=(16, 4))
        r += 1

        for title, body in TIPS:
            card = Card(scroll)
            card.grid(row=r, column=0, sticky="ew", padx=12, pady=4)
            card.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(card, text=title,
                         font=ctk.CTkFont(size=12, weight="bold"),
                         anchor="w").grid(row=0, column=0, sticky="w", padx=12, pady=(8, 2))
            ctk.CTkLabel(card, text=body,
                         font=ctk.CTkFont(size=12),
                         anchor="w", justify="left",
                         wraplength=590).grid(row=1, column=0, sticky="w",
                                              padx=12, pady=(0, 10))
            r += 1

        # spacer
        ctk.CTkLabel(scroll, text="").grid(row=r, column=0, pady=12)
