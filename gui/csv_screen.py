"""
gui/csv_screen.py
─────────────────
Project Eris – CSV Logs screen.

Displays all CSV log files currently on disk, grouped by:
  - Shared log files (connections without separate_csv)
  - Per-connection log files (one group per connection with separate_csv)

Each file row shows: filename, last-modified date, file size, and an
"Open" button that launches the file in the default program (usually
Excel or Notepad).

An "Open folder" button in the topbar opens the base log directory in
Windows Explorer.

The screen is refreshed every time the user navigates to it so the file
list is always current.
"""

import os
import subprocess
import customtkinter as ctk
from pathlib import Path
from logger import list_log_files
from gui.widgets import Card, GhostBtn, StatTile
from gui.theme import GREEN_PRIMARY, text_muted


def _fmt(b):
    if b < 1024:        return f"{b} B"
    if b < 1024**2:     return f"{b/1024:.1f} KB"
    return f"{b/1024**2:.1f} MB"


class CSVScreen(ctk.CTkFrame):
    def __init__(self, parent, config):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self._config = config
        self._build()

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        tb = ctk.CTkFrame(self, corner_radius=0,
                          fg_color=("white", "gray17"),
                          border_width=1, border_color=("gray85", "gray30"))
        tb.grid(row=0, column=0, sticky="ew")
        tb.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(tb, text="CSV Logs",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, padx=14, pady=10, sticky="w")
        GhostBtn(tb, text="Open folder", width=100,
                 command=self._open_base_folder).grid(
            row=0, column=2, padx=10, pady=6, sticky="e")

        scroll = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color="transparent")
        scroll.grid(row=1, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)
        self._scroll = scroll

    def refresh(self, config, conn_manager=None):
        self._config = config
        for w in self._scroll.winfo_children():
            w.destroy()

        # global log files
        shared_files = list_log_files(config)
        r = 0

        if shared_files:
            ctk.CTkLabel(self._scroll, text="Shared log files",
                         font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=("gray20", "gray80"),
                         anchor="w").grid(row=r, column=0, sticky="w", padx=14, pady=(12, 4))
            r += 1
            card = Card(self._scroll)
            card.grid(row=r, column=0, sticky="ew", padx=12, pady=4)
            card.grid_columnconfigure(0, weight=1)
            for i, f in enumerate(shared_files):
                self._file_row(card, i, f)
            r += 1

        # per-connection log files
        if conn_manager:
            for conn in conn_manager.connections.values():
                if not conn.separate_csv:
                    continue
                conn_files = list_log_files(config, conn.name)
                ctk.CTkLabel(self._scroll,
                             text=f"{conn.name} — separate logs",
                             font=ctk.CTkFont(size=13, weight="bold"),
                             text_color=("gray20", "gray80"),
                             anchor="w").grid(row=r, column=0, sticky="w", padx=14, pady=(12, 4))
                r += 1
                card = Card(self._scroll)
                card.grid(row=r, column=0, sticky="ew", padx=12, pady=4)
                card.grid_columnconfigure(0, weight=1)
                if conn_files:
                    for i, f in enumerate(conn_files):
                        self._file_row(card, i, f)
                else:
                    ctk.CTkLabel(card, text="No log files yet for this connection.",
                                 font=ctk.CTkFont(size=11), text_color=text_muted()).grid(
                        row=0, column=0, padx=12, pady=10)
                r += 1

        if r == 0:
            ctk.CTkLabel(self._scroll,
                         text="No log files found.\nStart logging on the Dashboard to create files.",
                         font=ctk.CTkFont(size=13), text_color=text_muted()).grid(
                row=0, column=0, pady=40)

    def _file_row(self, parent, row, f):
        fr = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=0)
        fr.grid(row=row * 2, column=0, sticky="ew", padx=8, pady=2)
        fr.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(fr, text="📄", font=ctk.CTkFont(size=13)).grid(
            row=0, column=0, padx=(4, 6))
        ctk.CTkLabel(fr, text=f["name"],
                     font=ctk.CTkFont(size=11, family="Courier"),
                     text_color=("gray40", "gray65"),
                     anchor="w").grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(fr, text=f["modified"],
                     font=ctk.CTkFont(size=11), text_color=text_muted()).grid(
            row=0, column=2, padx=8)
        ctk.CTkLabel(fr, text=_fmt(f["size"]),
                     font=ctk.CTkFont(size=11), text_color=text_muted()).grid(
            row=0, column=3, padx=4)
        GhostBtn(fr, text="Open", width=55, height=24,
                 command=lambda p=f["path"]: self._open(p)).grid(
            row=0, column=4, padx=4)

        # separator
        ctk.CTkFrame(parent, height=1,
                     fg_color=("gray88", "gray30"), corner_radius=0).grid(
            row=row * 2 + 1, column=0, sticky="ew", padx=8)

    def _open(self, path):
        try:
            os.startfile(path)
        except Exception:
            subprocess.Popen(["notepad", path])

    def _open_base_folder(self):
        folder = Path(self._config.get(
            "csv_folder", str(Path.home() / "ProjectEris" / "Logs")))
        folder.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(folder))
        except Exception:
            subprocess.Popen(["explorer", str(folder)])
