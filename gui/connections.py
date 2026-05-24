"""
gui/connections.py
──────────────────
Project Eris – Connection setup screen.

Allows the user to create, edit, and delete PLC connections.

Fields per connection:
  - Connection name (display label used throughout the app)
  - PLC type: Allen-Bradley (pylogix) or Siemens S7 (snap7)
  - IP address, Slot, Rack (S7 only)
  - Logging mode: Interval (timed) or Trigger (rising-edge BOOL tag)
    - Interval: configurable ms value, minimum 100 ms enforced
    - Trigger: tag name/address of the BOOL trigger tag
  - Separate CSV: write this connection's data to its own file
  - Tag list: address, data type, DB number (S7), byte offset (S7), enabled checkbox

The screen calls on_save / on_delete / on_test callbacks which are
wired up in App to the connection manager and config system.
"""

import uuid
import customtkinter as ctk
from tkinter import messagebox
from plc import MIN_INTERVAL_MS
from gui.widgets import Card, PrimaryBtn, GhostBtn, DangerBtn, hsep
from gui.theme import BLUE_PRIMARY, RED_PRIMARY, text_muted

# Data type options shown in the tag-list dropdowns
AB_TYPES = ["BOOL", "INT", "DINT", "REAL", "DWORD", "STRING"]
S7_TYPES = ["BOOL", "INT", "DINT", "REAL", "WORD", "DWORD"]


class ConnectionsScreen(ctk.CTkFrame):
    def __init__(self, parent, on_save, on_delete, on_test):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self.on_save   = on_save
        self.on_delete = on_delete
        self.on_test   = on_test
        self._current  = None
        self._tags     = []
        self._build()

    def _build(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        # topbar
        tb = ctk.CTkFrame(scroll, corner_radius=0,
                          fg_color=("white", "gray17"),
                          border_width=1, border_color=("gray85", "gray30"))
        tb.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        tb.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(tb, text="Connection setup",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, padx=14, pady=10, sticky="w")

        btns = ctk.CTkFrame(tb, fg_color="transparent")
        btns.grid(row=0, column=2, padx=10, sticky="e")
        PrimaryBtn(btns, text="Test connection", width=120,
                   command=self._do_test).pack(side="left", padx=3)
        GhostBtn(btns, text="Save", width=70,
                 command=self._do_save).pack(side="left", padx=2)
        self._del_btn = DangerBtn(btns, text="Delete", width=70,
                                   command=self._do_delete)
        self._del_btn.pack(side="left", padx=2)

        # ── connection basics ─────────────────────────────────────────────
        basics = Card(scroll)
        basics.grid(row=1, column=0, sticky="ew", padx=12, pady=4)
        basics.grid_columnconfigure((0, 1), weight=1)

        self._name_var = ctk.StringVar()
        self._type_var = ctk.StringVar(value="Allen-Bradley (pylogix)")
        self._ip_var   = ctk.StringVar()
        self._slot_var = ctk.StringVar(value="0")
        self._rack_var = ctk.StringVar(value="0")

        self._lf("Connection name", basics, 0, 0,
                  lambda p: ctk.CTkEntry(p, textvariable=self._name_var,
                                         placeholder_text="e.g. Line 1 – AB PLC"))
        self._lf("PLC type", basics, 0, 1,
                  lambda p: ctk.CTkOptionMenu(p, variable=self._type_var,
                                              values=["Allen-Bradley (pylogix)", "Siemens S7 (snap7)"],
                                              command=self._on_type))
        self._lf("IP address", basics, 2, 0,
                  lambda p: ctk.CTkEntry(p, textvariable=self._ip_var,
                                         placeholder_text="192.168.1.10"))
        self._lf("Slot", basics, 2, 1,
                  lambda p: ctk.CTkEntry(p, textvariable=self._slot_var))

        self._rack_lbl = ctk.CTkLabel(basics, text="Rack (S7 only)",
                                       font=ctk.CTkFont(size=11),
                                       text_color=text_muted(), anchor="w")
        self._rack_entry = ctk.CTkEntry(basics, textvariable=self._rack_var, width=80)

        # ── logging mode ──────────────────────────────────────────────────
        log_mode_card = Card(scroll)
        log_mode_card.grid(row=2, column=0, sticky="ew", padx=12, pady=4)
        log_mode_card.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(log_mode_card, text="Logging mode",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     anchor="w").grid(row=0, column=0, columnspan=2,
                                      sticky="w", padx=12, pady=(10, 6))

        self._log_mode_var = ctk.StringVar(value="interval")
        ctk.CTkRadioButton(log_mode_card, text="Interval logging",
                           variable=self._log_mode_var, value="interval",
                           command=self._on_log_mode).grid(
            row=1, column=0, sticky="w", padx=14, pady=2)
        ctk.CTkRadioButton(log_mode_card, text="Trigger logging",
                           variable=self._log_mode_var, value="trigger",
                           command=self._on_log_mode).grid(
            row=1, column=1, sticky="w", padx=14, pady=2)

        # interval sub-section
        self._interval_frame = ctk.CTkFrame(log_mode_card, fg_color="transparent")
        self._interval_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=4)
        self._interval_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self._interval_frame,
                     text=f"Interval (ms, min {MIN_INTERVAL_MS}ms)",
                     font=ctk.CTkFont(size=11), text_color=text_muted(),
                     anchor="w").grid(row=0, column=0, sticky="w")
        self._interval_var = ctk.StringVar(value="1000")
        self._interval_entry = ctk.CTkEntry(self._interval_frame,
                                             textvariable=self._interval_var,
                                             width=120)
        self._interval_entry.grid(row=1, column=0, sticky="w", pady=(2, 4))

        # trigger sub-section
        self._trigger_frame = ctk.CTkFrame(log_mode_card, fg_color="transparent")
        self._trigger_frame.grid(row=2, column=1, sticky="ew", padx=12, pady=4)
        self._trigger_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self._trigger_frame,
                     text="Trigger tag (BOOL)",
                     font=ctk.CTkFont(size=11), text_color=text_muted(),
                     anchor="w").grid(row=0, column=0, sticky="w")
        self._trigger_var = ctk.StringVar()
        self._trigger_entry = ctk.CTkEntry(self._trigger_frame,
                                            textvariable=self._trigger_var,
                                            placeholder_text="e.g. Log_Trigger or DB1.DBX0.0",
                                            state="disabled")
        self._trigger_entry.grid(row=1, column=0, sticky="ew", pady=(2, 4))

        # CSV options
        self._sep_csv_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(log_mode_card,
                        text="Separate CSV file for this connection",
                        variable=self._sep_csv_var,
                        font=ctk.CTkFont(size=12)).grid(
            row=3, column=0, columnspan=2, sticky="w", padx=14, pady=(4, 10))

        # ── tag list ──────────────────────────────────────────────────────
        tag_card = Card(scroll)
        tag_card.grid(row=3, column=0, sticky="ew", padx=12, pady=(4, 12))
        tag_card.grid_columnconfigure(0, weight=1)

        tag_hdr = ctk.CTkFrame(tag_card, fg_color="transparent")
        tag_hdr.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))
        tag_hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(tag_hdr, text="Tags to log",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     anchor="w").grid(row=0, column=0, sticky="w")
        GhostBtn(tag_hdr, text="+ Add tag", width=80, height=26,
                 command=self._add_row).grid(row=0, column=1, sticky="e")

        self._tag_scroll = ctk.CTkScrollableFrame(tag_card, height=200,
                                                   fg_color="transparent", corner_radius=0)
        self._tag_scroll.grid(row=1, column=0, sticky="ew", padx=4, pady=(0, 8))
        for i, txt in enumerate(["Tag / address", "Data type", "DB# (S7)", "Offset (S7)", "Log?", ""]):
            ctk.CTkLabel(self._tag_scroll, text=txt,
                         font=ctk.CTkFont(size=11), text_color=text_muted(),
                         anchor="w").grid(row=0, column=i, padx=6, pady=2, sticky="w")
        self._tag_scroll.grid_columnconfigure(0, weight=2)
        self._tag_scroll.grid_columnconfigure(1, weight=1)

    # ── form field helper ─────────────────────────────────────────────────
    def _lf(self, label, parent, row, col, factory):
        ctk.CTkLabel(parent, text=label,
                     font=ctk.CTkFont(size=11), text_color=text_muted(),
                     anchor="w").grid(row=row, column=col, sticky="w", padx=12, pady=(8, 0))
        w = factory(parent)
        w.grid(row=row + 1, column=col, sticky="ew", padx=12, pady=(2, 4))
        return w

    def _on_type(self, _val):
        if "Siemens" in self._type_var.get():
            self._rack_lbl.grid(row=4, column=0, sticky="w", padx=12, pady=(4, 0))
            self._rack_entry.grid(row=5, column=0, sticky="w", padx=12, pady=(2, 8))
        else:
            self._rack_lbl.grid_forget()
            self._rack_entry.grid_forget()

    def _on_log_mode(self):
        mode = self._log_mode_var.get()
        self._trigger_entry.configure(
            state="normal" if mode == "trigger" else "disabled")

    def _add_row(self, tag_cfg=None):
        row = len(self._tags) + 1
        addr_var    = ctk.StringVar(value=tag_cfg.get("address", "") if tag_cfg else "")
        type_var    = ctk.StringVar(value=tag_cfg.get("data_type", "REAL") if tag_cfg else "REAL")
        db_var      = ctk.StringVar(value=str(tag_cfg.get("db_number", 1)) if tag_cfg else "1")
        offset_var  = ctk.StringVar(value=str(tag_cfg.get("offset", 0)) if tag_cfg else "0")
        enabled_var = ctk.BooleanVar(value=tag_cfg.get("enabled", True) if tag_cfg else True)
        tag_id      = tag_cfg.get("id", str(uuid.uuid4())) if tag_cfg else str(uuid.uuid4())
        types = S7_TYPES if "Siemens" in self._type_var.get() else AB_TYPES

        a = ctk.CTkEntry(self._tag_scroll, textvariable=addr_var,
                         placeholder_text="TagName or address")
        a.grid(row=row, column=0, padx=3, pady=2, sticky="ew")

        t = ctk.CTkOptionMenu(self._tag_scroll, variable=type_var, values=types, width=85)
        t.grid(row=row, column=1, padx=3, pady=2, sticky="ew")

        d = ctk.CTkEntry(self._tag_scroll, textvariable=db_var, width=55)
        d.grid(row=row, column=2, padx=3, pady=2, sticky="w")

        o = ctk.CTkEntry(self._tag_scroll, textvariable=offset_var, width=55)
        o.grid(row=row, column=3, padx=3, pady=2, sticky="w")

        c = ctk.CTkCheckBox(self._tag_scroll, text="", variable=enabled_var, width=30)
        c.grid(row=row, column=4, padx=3, pady=2)

        rec = {"_id": tag_id, "_addr": addr_var, "_type": type_var,
               "_db": db_var, "_offset": offset_var, "_enabled": enabled_var,
               "_widgets": [a, t, d, o, c]}

        def remove():
            self._tags = [x for x in self._tags if x["_id"] != tag_id]
            for w in rec["_widgets"] + [del_btn]:
                try:
                    w.destroy()
                except Exception:
                    pass

        del_btn = GhostBtn(self._tag_scroll, text="✕", width=28, height=26,
                           text_color=RED_PRIMARY, command=remove)
        del_btn.grid(row=row, column=5, padx=3, pady=2)
        rec["_widgets"].append(del_btn)
        self._tags.append(rec)

    def _collect_tags(self):
        tags = []
        for t in self._tags:
            addr = t["_addr"].get().strip()
            if addr:
                tags.append({
                    "id":         t["_id"],
                    "address":    addr,
                    "data_type":  t["_type"].get(),
                    "db_number":  t["_db"].get(),
                    "offset":     t["_offset"].get(),
                    "enabled":    t["_enabled"].get(),
                })
        return tags

    def _validate_interval(self):
        try:
            ms = int(self._interval_var.get())
            if ms < MIN_INTERVAL_MS:
                self._interval_var.set(str(MIN_INTERVAL_MS))
                messagebox.showwarning(
                    "Interval too low",
                    f"Minimum interval is {MIN_INTERVAL_MS}ms. Value set to {MIN_INTERVAL_MS}ms."
                )
                return MIN_INTERVAL_MS
            return ms
        except ValueError:
            self._interval_var.set("1000")
            return 1000

    def load_connection(self, conn_cfg):
        self._current = conn_cfg
        for w in self._tag_scroll.winfo_children():
            w.destroy()
        self._tags = []
        # redraw header
        for i, txt in enumerate(["Tag / address", "Data type", "DB# (S7)", "Offset (S7)", "Log?", ""]):
            ctk.CTkLabel(self._tag_scroll, text=txt,
                         font=ctk.CTkFont(size=11), text_color=text_muted(),
                         anchor="w").grid(row=0, column=i, padx=6, pady=2, sticky="w")

        if conn_cfg is None:
            self._name_var.set("")
            self._ip_var.set("")
            self._slot_var.set("0")
            self._rack_var.set("0")
            self._type_var.set("Allen-Bradley (pylogix)")
            self._log_mode_var.set("interval")
            self._interval_var.set("1000")
            self._trigger_var.set("")
            self._sep_csv_var.set(False)
            self._del_btn.configure(state="disabled")
        else:
            self._name_var.set(conn_cfg.get("name", ""))
            self._ip_var.set(conn_cfg.get("ip", ""))
            self._slot_var.set(str(conn_cfg.get("slot", 0)))
            self._rack_var.set(str(conn_cfg.get("rack", 0)))
            pt = conn_cfg.get("plc_type", "ab")
            self._type_var.set("Allen-Bradley (pylogix)" if pt == "ab" else "Siemens S7 (snap7)")
            self._log_mode_var.set(conn_cfg.get("log_mode", "interval"))
            self._interval_var.set(str(conn_cfg.get("log_interval_ms", 1000)))
            self._trigger_var.set(conn_cfg.get("trigger_tag", ""))
            self._sep_csv_var.set(conn_cfg.get("separate_csv", False))
            self._on_type(None)
            self._on_log_mode()
            self._del_btn.configure(state="normal")
            for tag in conn_cfg.get("tags", []):
                self._add_row(tag)

    def _build_cfg(self):
        return {
            "id":              self._current["id"] if self._current else "",
            "name":            self._name_var.get().strip(),
            "plc_type":        "ab" if "Allen" in self._type_var.get() else "s7",
            "ip":              self._ip_var.get().strip(),
            "slot":            self._slot_var.get(),
            "rack":            self._rack_var.get(),
            "log_mode":        self._log_mode_var.get(),
            "log_interval_ms": self._validate_interval(),
            "trigger_tag":     self._trigger_var.get().strip(),
            "separate_csv":    self._sep_csv_var.get(),
            "tags":            self._collect_tags(),
        }

    def _do_save(self):
        cfg = self._build_cfg()
        if not cfg["name"] or not cfg["ip"]:
            messagebox.showwarning("Missing fields", "Name and IP address are required.")
            return
        self.on_save(cfg)
        self._current = cfg

    def _do_delete(self):
        if self._current:
            if messagebox.askyesno("Delete", f"Delete '{self._current['name']}'?"):
                self.on_delete(self._current["id"])

    def _do_test(self):
        ip = self._ip_var.get().strip()
        if not ip:
            messagebox.showwarning("Missing IP", "Enter an IP address first.")
            return
        cfg = self._build_cfg()
        cfg["id"] = cfg["id"] or str(uuid.uuid4())
        self.on_test(cfg)
