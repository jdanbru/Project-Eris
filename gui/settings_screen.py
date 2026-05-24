"""
gui/settings_screen.py
──────────────────────
Project Eris – Settings screen.

Allows the user to configure application-wide preferences:

  Logging defaults:
    - Default log interval in milliseconds
    - Timestamp format: ISO 8601 or Excel-friendly

  CSV save folder:
    - Text field showing the current path
    - Browse button to open a folder picker dialog

  Startup behaviour:
    - Auto-connect on launch (connect all PLCs when the app starts)
    - Auto-start logging on launch (begin logging immediately after connecting)
    - Minimize to system tray on close (instead of exiting)

Settings are saved to disk when the user clicks "Save settings".
The on_save callback is wired in App to update the live config dict and
persist it to config.json.
"""

import customtkinter as ctk
from tkinter import filedialog
from pathlib import Path
from gui.widgets import Card, PrimaryBtn, GhostBtn
from gui.theme import text_muted


class SettingsScreen(ctk.CTkFrame):
    def __init__(self, parent, config, on_save):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self._config = config
        self.on_save = on_save
        self._build()

    def _build(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        tb = ctk.CTkFrame(scroll, corner_radius=0,
                          fg_color=("white", "gray17"),
                          border_width=1, border_color=("gray85", "gray30"))
        tb.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        tb.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(tb, text="Settings",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, padx=14, pady=10, sticky="w")
        PrimaryBtn(tb, text="Save settings", width=110,
                   command=self._do_save).grid(
            row=0, column=2, padx=10, pady=6, sticky="e")

        # logging card
        log_card = Card(scroll)
        log_card.grid(row=1, column=0, sticky="ew", padx=12, pady=4)
        log_card.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(log_card, text="Logging defaults",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     anchor="w").grid(row=0, column=0, columnspan=2,
                                      sticky="w", padx=12, pady=(10, 6))

        ctk.CTkLabel(log_card, text="Default log interval (ms)",
                     font=ctk.CTkFont(size=11), text_color=text_muted(),
                     anchor="w").grid(row=1, column=0, sticky="w", padx=12)
        self._interval_var = ctk.StringVar(
            value=str(self._config.get("log_interval", 1.0) * 1000))
        ctk.CTkEntry(log_card, textvariable=self._interval_var).grid(
            row=2, column=0, sticky="ew", padx=12, pady=(2, 10))

        ctk.CTkLabel(log_card, text="Timestamp format",
                     font=ctk.CTkFont(size=11), text_color=text_muted(),
                     anchor="w").grid(row=1, column=1, sticky="w", padx=12)
        self._ts_var = ctk.StringVar(value=(
            "ISO 8601 (2026-05-24T08:31:00)"
            if self._config.get("timestamp_format", "iso") == "iso"
            else "Excel friendly (24/05/2026 08:31:00)"
        ))
        ctk.CTkOptionMenu(log_card, variable=self._ts_var, values=[
            "ISO 8601 (2026-05-24T08:31:00)",
            "Excel friendly (24/05/2026 08:31:00)",
        ]).grid(row=2, column=1, sticky="ew", padx=12, pady=(2, 10))

        # folder card
        folder_card = Card(scroll)
        folder_card.grid(row=2, column=0, sticky="ew", padx=12, pady=4)
        folder_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(folder_card, text="CSV save folder",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     anchor="w").grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))

        row_f = ctk.CTkFrame(folder_card, fg_color="transparent")
        row_f.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))
        row_f.grid_columnconfigure(0, weight=1)

        self._folder_var = ctk.StringVar(value=self._config.get(
            "csv_folder", str(Path.home() / "ProjectEris" / "Logs")))
        ctk.CTkEntry(row_f, textvariable=self._folder_var).grid(
            row=0, column=0, sticky="ew", padx=(0, 6))
        GhostBtn(row_f, text="Browse", width=75, height=32,
                 command=self._browse).grid(row=0, column=1)

        # startup card
        startup_card = Card(scroll)
        startup_card.grid(row=3, column=0, sticky="ew", padx=12, pady=8)
        startup_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(startup_card, text="Startup behaviour",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     anchor="w").grid(row=0, column=0, sticky="w", padx=12, pady=(10, 6))

        self._auto_conn = ctk.BooleanVar(value=self._config.get("auto_connect", True))
        self._auto_log  = ctk.BooleanVar(value=self._config.get("auto_log", False))
        self._tray      = ctk.BooleanVar(value=self._config.get("minimize_to_tray", False))

        for i, (text, var) in enumerate([
            ("Auto-connect on launch",           self._auto_conn),
            ("Auto-start logging on launch",     self._auto_log),
            ("Minimize to system tray on close", self._tray),
        ]):
            ctk.CTkCheckBox(startup_card, text=text, variable=var,
                            font=ctk.CTkFont(size=12)).grid(
                row=i + 1, column=0, sticky="w", padx=14, pady=3)

        ctk.CTkLabel(startup_card, text="").grid(row=4, column=0, pady=4)

    def _browse(self):
        f = filedialog.askdirectory(title="Select CSV save folder")
        if f:
            self._folder_var.set(f)

    def _do_save(self):
        try:
            ms = int(self._interval_var.get())
        except ValueError:
            ms = 1000
        self.on_save({
            "log_interval":      ms / 1000.0,
            "timestamp_format":  "iso" if "ISO" in self._ts_var.get() else "excel",
            "csv_folder":        self._folder_var.get().strip(),
            "auto_connect":      self._auto_conn.get(),
            "auto_log":          self._auto_log.get(),
            "minimize_to_tray":  self._tray.get(),
        })
