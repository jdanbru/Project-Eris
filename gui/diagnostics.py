"""
gui/diagnostics.py
──────────────────
Project Eris – Diagnostics screen.

Shows live diagnostic information for every configured PLC connection.
One panel is rendered per connection, containing:
  - Connection name, type badge, and current status
  - A monospaced text box with device details (product name, firmware,
    serial number, PLC time, tag count for AB; CPU state, PDU length for S7)
  - A "Refresh" button to re-query the PLC on demand

For Siemens S7 connections an additional warning panel is shown with a
button to call get_cpu_info().  This call is gated behind a visible
warning because it has been documented to crash some S7-300 PLCs.

All diagnostic reads happen on background threads so the UI stays
responsive while waiting for the PLC to respond.
"""

import threading
import customtkinter as ctk
from tkinter import messagebox
from gui.widgets import Card, PrimaryBtn, GhostBtn, hsep
from gui.theme import (
    BLUE_PRIMARY, GREEN_PRIMARY, RED_PRIMARY, AMBER_PRIMARY,
    badge_colors, text_muted, STATUS_COLORS,
)


def _fmt_row(label, value):
    return f"{label:<22}{value}"


class DiagnosticsScreen(ctk.CTkFrame):
    def __init__(self, parent, get_conn_manager):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self.get_cm = get_conn_manager
        self._build()

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        tb = ctk.CTkFrame(self, corner_radius=0,
                          fg_color=("white", "gray17"),
                          border_width=1, border_color=("gray85", "gray30"))
        tb.grid(row=0, column=0, sticky="ew")
        tb.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(tb, text="Diagnostics",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, padx=14, pady=10, sticky="w")
        ctk.CTkLabel(tb, text="Live connection diagnostics and device info",
                     font=ctk.CTkFont(size=11), text_color=text_muted()).grid(
            row=0, column=1, padx=4, pady=10, sticky="w")
        PrimaryBtn(tb, text="↻  Refresh all", width=110,
                   command=self.refresh_all).grid(row=0, column=2, padx=10, pady=6, sticky="e")

        self._scroll = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color="transparent")
        self._scroll.grid(row=1, column=0, sticky="nsew")
        self._scroll.grid_columnconfigure(0, weight=1)
        self._panels = {}

    def refresh_all(self):
        cm = self.get_cm()
        if not cm:
            return
        # clear old panels
        for w in self._scroll.winfo_children():
            w.destroy()
        self._panels = {}

        if not cm.connections:
            ctk.CTkLabel(self._scroll,
                         text="No connections configured.\nGo to Connections to add one.",
                         font=ctk.CTkFont(size=13), text_color=text_muted()).pack(pady=40)
            return

        for i, (cid, conn) in enumerate(cm.connections.items()):
            panel = self._make_panel(conn)
            panel.grid(row=i, column=0, sticky="ew", padx=12, pady=6)
            self._panels[cid] = panel

    def _make_panel(self, conn):
        bc    = badge_colors(conn.plc_type)
        panel = Card(self._scroll)
        panel.grid_columnconfigure(0, weight=1)

        # header row
        hdr = ctk.CTkFrame(panel, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))
        hdr.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(hdr,
                     text="AB" if conn.plc_type == "ab" else "S7",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=bc["fg"], fg_color=bc["bg"],
                     corner_radius=4, width=26, height=18).grid(row=0, column=0, padx=(0, 6))

        ctk.CTkLabel(hdr,
                     text=conn.name,
                     font=ctk.CTkFont(size=13, weight="bold"),
                     anchor="w").grid(row=0, column=1, sticky="w")

        status_color = STATUS_COLORS.get(conn.status, "#888780")
        ctk.CTkLabel(hdr,
                     text=f"● {conn.status.capitalize()}",
                     font=ctk.CTkFont(size=11), text_color=status_color).grid(
            row=0, column=2, padx=6)

        refresh_btn = GhostBtn(hdr, text="Refresh", width=70, height=26,
                               command=lambda c=conn, p=panel: self._refresh_one(c, p))
        refresh_btn.grid(row=0, column=3, padx=4)

        # info box
        info_box = ctk.CTkTextbox(panel, height=160, font=ctk.CTkFont(size=11, family="Courier"),
                                   fg_color=("gray95", "gray20"), corner_radius=4)
        info_box.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 4))
        info_box.insert("end", self._diag_text(conn))
        info_box.configure(state="disabled")

        # S7-only: advanced button with warning
        if conn.plc_type == "s7":
            warn_frame = ctk.CTkFrame(panel, fg_color=("#FEF9E7", "#3D3010"), corner_radius=4)
            warn_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 4))
            warn_frame.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                warn_frame,
                text="⚠  get_cpu_info() can crash some S7-300 PLCs. Only use on S7-1200/1500.",
                font=ctk.CTkFont(size=11),
                text_color=(AMBER_PRIMARY, "#FAC775"),
                anchor="w",
            ).grid(row=0, column=0, sticky="w", padx=10, pady=4)
            GhostBtn(warn_frame, text="Get full CPU info (risk)", width=170, height=26,
                     text_color=AMBER_PRIMARY,
                     command=lambda c=conn, ib=info_box: self._get_s7_full(c, ib)).grid(
                row=0, column=1, padx=8, pady=4)

        return panel

    def _diag_text(self, conn):
        d = conn.get_diagnostics()
        lines = [
            f"IP address      : {d.get('ip','—')}",
            f"PLC type        : {'Allen-Bradley' if d.get('plc_type')=='ab' else 'Siemens S7'}",
            f"Status          : {d.get('status','—')}",
            f"Last error      : {d.get('error','none') or 'none'}",
            f"Timestamp       : {d.get('timestamp','—')}",
            "─" * 44,
        ]
        # AB fields
        for k, label in [
            ("product_name", "Product name"),
            ("revision",     "Firmware rev."),
            ("vendor",       "Vendor"),
            ("serial",       "Serial number"),
            ("device_type",  "Device type"),
            ("plc_time",     "PLC time"),
            ("tag_count",    "Tag count"),
        ]:
            if k in d:
                lines.append(f"{label:<16}: {d[k]}")
        # S7 fields
        for k, label in [
            ("cpu_state",  "CPU state"),
            ("pdu_length", "PDU length"),
        ]:
            if k in d:
                lines.append(f"{label:<16}: {d[k]}")

        if not any(k in d for k in ["product_name","cpu_state"]):
            lines.append("(Connect to PLC to see device info)")
        return "\n".join(lines)

    def _refresh_one(self, conn, panel):
        def _do():
            text = self._diag_text(conn)
            self.after(0, lambda: self._update_textbox(panel, text))
        threading.Thread(target=_do, daemon=True).start()

    def _get_s7_full(self, conn, info_box):
        def _do():
            result = conn.get_s7_cpu_info()
            extra  = "\n─" * 22 + "\nFull CPU info:\n"
            for k, v in result.items():
                extra += f"{k:<14}: {v}\n"
            self.after(0, lambda: self._append_textbox(info_box, extra))
        threading.Thread(target=_do, daemon=True).start()

    def _update_textbox(self, panel, text):
        for child in panel.winfo_children():
            if isinstance(child, ctk.CTkTextbox):
                child.configure(state="normal")
                child.delete("1.0", "end")
                child.insert("end", text)
                child.configure(state="disabled")

    def _append_textbox(self, box, text):
        box.configure(state="normal")
        box.insert("end", text)
        box.configure(state="disabled")
