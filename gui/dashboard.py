"""
gui/dashboard.py
────────────────
Project Eris – Dashboard screen.

Layout (v4.3):
  Row 0 – topbar (title + Connect All + Start/Stop)
  Row 1 – stat tiles (4 across)
  Row 2 – two columns: [Live tag table] | [Active log file card]
  Row 3 – full-width trend chart (select a tag in the table to plot)
"""

import customtkinter as ctk
from tkinter import ttk
from collections import defaultdict, deque
from gui.theme import (
    BLUE_PRIMARY, GREEN_PRIMARY, GREEN_LIGHT,
    RED_PRIMARY, text_muted,
)
from gui.widgets import Card, StatTile, LogPill, GhostBtn, SuccessBtn

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

# Live trend keeps the last 60 readings per tag
MAX_TREND = 60


class DashboardScreen(ctk.CTkFrame):
    """
    Dashboard layout:
      - Stat tiles row
      - Middle row: Live Tag Values (left) | Active CSV file card (right, same height)
      - Bottom: full-width trend chart for the selected tag
    """

    def __init__(self, parent, on_toggle_log, on_connect):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self.on_toggle_log = on_toggle_log
        self.on_connect    = on_connect
        self._logging      = False
        self._trend_data   = defaultdict(lambda: deque(maxlen=MAX_TREND))
        self._sel_tag_key  = None
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        # Row 0 = topbar (fixed), rows 1-3 distributed below
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)   # stat tiles
        self.grid_rowconfigure(2, weight=2)   # tag table + csv card
        self.grid_rowconfigure(3, weight=3)   # trend chart (taller than mid)

        # ── topbar ────────────────────────────────────────────────────────
        tb = ctk.CTkFrame(self, corner_radius=0,
                          fg_color="white",
                          border_width=1, border_color="gray85")
        tb.grid(row=0, column=0, sticky="ew")
        tb.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(tb, text="Dashboard",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, padx=14, pady=10, sticky="w")

        actions = ctk.CTkFrame(tb, fg_color="transparent")
        actions.grid(row=0, column=2, padx=10, pady=6, sticky="e")

        self._pill = LogPill(actions)
        self._pill.pack(side="left", padx=8)

        GhostBtn(actions, text="Connect all", width=95,
                 command=self.on_connect).pack(side="left", padx=4)

        self._log_btn = SuccessBtn(actions, text="▶  Start logging", width=120,
                                   command=self.on_toggle_log)
        self._log_btn.pack(side="left", padx=4)

        # ── stat tiles ────────────────────────────────────────────────────
        stats = ctk.CTkFrame(self, fg_color="transparent")
        stats.grid(row=1, column=0, sticky="ew", padx=12, pady=(10, 6))
        for i in range(4):
            stats.grid_columnconfigure(i, weight=1)

        self._s_tags     = StatTile(stats, "Tags logging",   "0",  BLUE_PRIMARY)
        self._s_interval = StatTile(stats, "Log interval",   "—")
        self._s_rows     = StatTile(stats, "CSV rows total", "0")
        self._s_errors   = StatTile(stats, "Errors",         "0")
        for i, t in enumerate([self._s_tags, self._s_interval,
                                self._s_rows, self._s_errors]):
            t.grid(row=0, column=i, sticky="ew", padx=4, pady=2)

        # ── middle row: live tag table (left) + csv card (right) ──────────
        mid = ctk.CTkFrame(self, fg_color="transparent")
        mid.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 6))
        mid.grid_columnconfigure(0, weight=3)
        mid.grid_columnconfigure(1, weight=2)
        mid.grid_rowconfigure(0, weight=1)

        # ── left: live tag table ──────────────────────────────────────────
        left = Card(mid)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        tag_hdr = ctk.CTkFrame(left, fg_color="transparent")
        tag_hdr.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))
        tag_hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(tag_hdr, text="Live tag values",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     anchor="w").grid(row=0, column=0, sticky="w")
        self._update_lbl = ctk.CTkLabel(tag_hdr, text="",
                                         font=ctk.CTkFont(size=11),
                                         text_color=text_muted())
        self._update_lbl.grid(row=0, column=1, sticky="e")

        # Treeview style — light mode only (dark mode removed)
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Eris.Treeview",
                        background="white", foreground="#111",
                        rowheight=26, fieldbackground="white",
                        font=("TkDefaultFont", 11))
        style.configure("Eris.Treeview.Heading",
                        font=("TkDefaultFont", 10, "bold"),
                        background="#F1EFE8", foreground="#444")
        style.map("Eris.Treeview", background=[("selected", "#B5D4F4")])

        self._tree = ttk.Treeview(left,
                                   columns=("tag", "value", "type", "source", "mode"),
                                   show="headings",
                                   style="Eris.Treeview",
                                   height=10)
        for col, w, txt in [
            ("tag",    160, "Tag name"),
            ("value",   90, "Value"),
            ("type",    60, "Type"),
            ("source",  95, "Connection"),
            ("mode",    70, "Log mode"),
        ]:
            self._tree.heading(col, text=txt)
            self._tree.column(col, width=w,
                              anchor="w" if col in ("tag", "source") else "center")
        self._tree.grid(row=1, column=0, sticky="nsew", padx=1, pady=(0, 1))
        self._tree.bind("<<TreeviewSelect>>", self._on_sel)

        # ── right: active CSV file card (same height as tag table) ────────
        csv_card = Card(mid)
        csv_card.grid(row=0, column=1, sticky="nsew")
        csv_card.grid_columnconfigure(0, weight=1)
        csv_card.grid_rowconfigure(3, weight=1)   # push content to top, fill rest

        ctk.CTkLabel(csv_card, text="Active log file",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     anchor="w").grid(row=0, column=0, sticky="w",
                                      padx=12, pady=(10, 4))

        self._csv_name = ctk.CTkLabel(csv_card, text="—",
                                       font=ctk.CTkFont(size=11, family="Courier"),
                                       text_color=text_muted(), anchor="w",
                                       wraplength=200)
        self._csv_name.grid(row=1, column=0, sticky="w", padx=12)

        self._csv_info = ctk.CTkLabel(csv_card, text="Not logging",
                                       font=ctk.CTkFont(size=11),
                                       text_color=text_muted(), anchor="w",
                                       justify="left", wraplength=200)
        self._csv_info.grid(row=2, column=0, sticky="nw", padx=12, pady=(4, 8))

        # ── bottom: full-width trend chart ────────────────────────────────
        trend_card = Card(self)
        trend_card.grid(row=3, column=0, sticky="nsew", padx=12, pady=(0, 10))
        trend_card.grid_rowconfigure(1, weight=1)
        trend_card.grid_columnconfigure(0, weight=1)

        trend_hdr = ctk.CTkFrame(trend_card, fg_color="transparent")
        trend_hdr.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))
        trend_hdr.grid_columnconfigure(0, weight=1)

        self._trend_title = ctk.CTkLabel(trend_hdr,
                                          text="Live trend — click a tag in the table above",
                                          font=ctk.CTkFont(size=12, weight="bold"),
                                          anchor="w")
        self._trend_title.grid(row=0, column=0, sticky="w")

        if HAS_MPL:
            # Full-width figure — wider aspect ratio since it spans the whole screen
            self._fig, self._ax = plt.subplots(figsize=(9, 2.4))
            self._fig.patch.set_facecolor("#F8F8F6")
            self._ax.set_facecolor("#F8F8F6")
            self._ax.tick_params(labelsize=8)
            self._ax.spines["top"].set_visible(False)
            self._ax.spines["right"].set_visible(False)
            self._ax.set_xlabel("Cycle Number", fontsize=9)
            self._ax.set_ylabel("Recorded Value", fontsize=9)
            self._fig.tight_layout(pad=1.2)

            self._canvas = FigureCanvasTkAgg(self._fig, master=trend_card)
            self._canvas.get_tk_widget().grid(row=1, column=0, sticky="nsew",
                                               padx=4, pady=(0, 6))
        else:
            ctk.CTkLabel(trend_card,
                         text="Install matplotlib for trend chart\npip install matplotlib",
                         text_color=text_muted(),
                         font=ctk.CTkFont(size=11)).grid(row=1, column=0, pady=20)

    # ── public API ────────────────────────────────────────────────────────

    def set_logging(self, logging: bool):
        """Toggle Start/Stop button appearance and status pill."""
        self._logging = logging
        self._pill.set_logging(logging)
        if logging:
            self._log_btn.configure(
                text="■  Stop logging",
                fg_color=RED_PRIMARY, hover_color="#791F1F",
                text_color="#FCEBEB")
        else:
            self._log_btn.configure(
                text="▶  Start logging",
                fg_color=GREEN_PRIMARY, hover_color="#27500A",
                text_color=GREEN_LIGHT)

    def update(self, conns_info: list, stats: dict):
        """Called every 800ms by App to refresh all live data."""
        total_tags = 0
        errors     = sum(1 for c in conns_info if c["status"] == "error")

        self._tree.delete(*self._tree.get_children())
        for conn in conns_info:
            mode_lbl = "Trigger" if conn.get("log_mode") == "trigger" else "Interval"
            for tag in conn.get("tags", []):
                if not tag.get("enabled", True):
                    continue
                addr = tag["address"]
                val  = conn["values"].get(addr, "—")
                if isinstance(val, float):
                    val = f"{val:.4g}"
                self._tree.insert("", "end", values=(
                    addr, val,
                    tag.get("data_type", "—"),
                    conn["name"],
                    mode_lbl,
                ))
                total_tags += 1
                key = f"{conn['id']}::{addr}"
                try:
                    self._trend_data[key].append(float(val))
                except (ValueError, TypeError):
                    pass

        # Update stat tiles
        self._s_tags.set(total_tags, BLUE_PRIMARY)
        iv = stats.get("interval_ms")
        self._s_interval.set(f"{iv/1000:.3f} s" if iv else "—")
        self._s_rows.set(f"{stats.get('total_rows', 0):,}")
        self._s_errors.set(str(errors),
                           color=RED_PRIMARY if errors else ("gray10", "gray90"))
        self._update_lbl.configure(text="Live")

        # Update CSV card
        if stats.get("running"):
            fname = stats.get("shared_filename") or ""
            rows  = stats.get("total_rows", 0)
            size  = stats.get("total_size", 0)
            size_str = (f"{size/1024:.1f} KB" if size < 1024*1024
                        else f"{size/1024/1024:.1f} MB") if size else ""
            self._csv_name.configure(text=fname or "Per-connection files")
            info = f"Started {stats.get('start_time', '')}\n{rows:,} rows"
            if size_str:
                info += f"  ·  {size_str}"
            self._csv_info.configure(text=info)
        else:
            self._csv_name.configure(text="—")
            self._csv_info.configure(text="Not logging")

        self._draw_trend()

    def _on_sel(self, _event):
        """User clicked a row in the tag table — set that tag as the trend subject."""
        sel = self._tree.selection()
        if sel:
            tag_name = self._tree.item(sel[0])["values"][0]
            self._sel_tag_key = None
            for k in self._trend_data:
                if tag_name in k:
                    self._sel_tag_key = k
                    break
            self._trend_title.configure(text=f"Live trend — {tag_name}")

    def _draw_trend(self):
        """Redraw the full-width trend chart for the selected tag."""
        if not HAS_MPL or not self._sel_tag_key:
            return
        data = list(self._trend_data.get(self._sel_tag_key, []))
        if len(data) < 2:
            return
        self._ax.clear()
        self._ax.plot(data, color=BLUE_PRIMARY, linewidth=1.5)
        self._ax.fill_between(range(len(data)), data,
                               alpha=0.08, color=BLUE_PRIMARY)
        self._ax.set_facecolor("#F8F8F6")
        self._ax.tick_params(labelsize=8)
        self._ax.spines["top"].set_visible(False)
        self._ax.spines["right"].set_visible(False)
        self._ax.set_xlabel("Cycle Number", fontsize=9)
        self._ax.set_ylabel("Recorded Value", fontsize=9)
        self._fig.tight_layout(pad=1.2)
        self._canvas.draw()
