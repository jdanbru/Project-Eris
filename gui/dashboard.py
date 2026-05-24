"""
gui/dashboard.py
────────────────
Project Eris – Dashboard screen.

The first screen the user sees.  Shows:
  - Four stat tiles: tags logging, log interval, CSV row count, error count
  - Live tag value table (all enabled tags across all connections, updates
    every 800 ms while the poll loop is running)
  - Trend chart for the currently selected tag (matplotlib line chart)
  - Active CSV file info panel (filename, start time, row count, file size)
  - Start/Stop logging button and Connect All button in the topbar

The dashboard is purely a display — it does not drive any polling itself.
The App class calls update() on a timer and passes fresh data each time.
"""

import customtkinter as ctk
from tkinter import ttk
from collections import defaultdict, deque
from gui.theme import (
    BLUE_PRIMARY, GREEN_PRIMARY, GREEN_LIGHT,
    RED_PRIMARY, AMBER_PRIMARY,
    badge_colors, card_bg, surface_bg, border_color, text_muted,
)
from gui.widgets import (
    Card, StatTile, LogPill, PrimaryBtn, GhostBtn, DangerBtn, SuccessBtn, hsep,
)

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

# Number of data points kept in memory for the trend chart per tag
MAX_TREND = 60


class DashboardScreen(ctk.CTkFrame):
    def __init__(self, parent, on_toggle_log, on_connect):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self.on_toggle_log = on_toggle_log
        self.on_connect    = on_connect
        self._logging      = False
        self._trend_data   = defaultdict(lambda: deque(maxlen=MAX_TREND))
        self._sel_tag_key  = None
        self._build()

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── topbar ────────────────────────────────────────────────────────
        tb = ctk.CTkFrame(self, corner_radius=0,
                          fg_color=("white", "gray17"),
                          border_width=1, border_color=("gray85", "gray30"))
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

        # ── scrollable content ────────────────────────────────────────────
        scroll = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color="transparent")
        scroll.grid(row=1, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        # stat row
        stats = ctk.CTkFrame(scroll, fg_color="transparent")
        stats.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        for i in range(4):
            stats.grid_columnconfigure(i, weight=1)

        self._s_tags     = StatTile(stats, "Tags logging", "0", BLUE_PRIMARY)
        self._s_interval = StatTile(stats, "Log interval", "—")
        self._s_rows     = StatTile(stats, "CSV rows total", "0")
        self._s_errors   = StatTile(stats, "Errors", "0")
        for i, t in enumerate([self._s_tags, self._s_interval, self._s_rows, self._s_errors]):
            t.grid(row=0, column=i, sticky="ew", padx=4, pady=2)

        # two-col layout
        mid = ctk.CTkFrame(scroll, fg_color="transparent")
        mid.grid(row=1, column=0, sticky="ew", padx=12, pady=6)
        mid.grid_columnconfigure(0, weight=3)
        mid.grid_columnconfigure(1, weight=2)

        # left: live tag table
        left = Card(mid)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(left, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))
        hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr, text="Live tag values",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     anchor="w").grid(row=0, column=0, sticky="w")
        self._update_lbl = ctk.CTkLabel(hdr, text="",
                                         font=ctk.CTkFont(size=11),
                                         text_color=text_muted())
        self._update_lbl.grid(row=0, column=1, sticky="e")

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
                                   height=12)
        for col, w, txt in [
            ("tag",    160, "Tag name"),
            ("value",   90, "Value"),
            ("type",    60, "Type"),
            ("source",  95, "Connection"),
            ("mode",    70, "Log mode"),
        ]:
            self._tree.heading(col, text=txt)
            self._tree.column(col, width=w, anchor="w" if col in ("tag","source") else "center")
        self._tree.grid(row=1, column=0, sticky="nsew", padx=1, pady=(0, 1))
        self._tree.bind("<<TreeviewSelect>>", self._on_sel)

        # right col
        right = ctk.CTkFrame(mid, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(0, weight=2)
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        # trend
        trend = Card(right)
        trend.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        trend.grid_rowconfigure(1, weight=1)
        trend.grid_columnconfigure(0, weight=1)

        self._trend_title = ctk.CTkLabel(trend, text="Trend — select a tag",
                                          font=ctk.CTkFont(size=12, weight="bold"),
                                          anchor="w")
        self._trend_title.grid(row=0, column=0, sticky="w", padx=12, pady=(8, 2))

        if HAS_MPL:
            self._fig, self._ax = plt.subplots(figsize=(3.4, 2.0))
            self._fig.patch.set_facecolor("#F8F8F6")
            self._ax.set_facecolor("#F8F8F6")
            self._ax.tick_params(labelsize=8)
            self._ax.spines["top"].set_visible(False)
            self._ax.spines["right"].set_visible(False)
            self._fig.tight_layout(pad=1.0)
            self._canvas = FigureCanvasTkAgg(self._fig, master=trend)
            self._canvas.get_tk_widget().grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 4))
        else:
            ctk.CTkLabel(trend, text="Install matplotlib\nfor trend chart",
                         text_color=text_muted(),
                         font=ctk.CTkFont(size=11)).grid(row=1, column=0, pady=20)

        # active CSV panel
        csv_card = Card(right)
        csv_card.grid(row=1, column=0, sticky="nsew")
        csv_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(csv_card, text="Active log file",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     anchor="w").grid(row=0, column=0, sticky="w", padx=12, pady=(8, 2))
        self._csv_name = ctk.CTkLabel(csv_card, text="—",
                                       font=ctk.CTkFont(size=11, family="Courier"),
                                       text_color=text_muted(), anchor="w")
        self._csv_name.grid(row=1, column=0, sticky="w", padx=12)
        self._csv_info = ctk.CTkLabel(csv_card, text="Not logging",
                                       font=ctk.CTkFont(size=11),
                                       text_color=text_muted(), anchor="w")
        self._csv_info.grid(row=2, column=0, sticky="w", padx=12, pady=(0, 8))

    # ── public API ────────────────────────────────────────────────────────
    def set_logging(self, logging):
        self._logging = logging
        self._pill.set_logging(logging)
        if logging:
            self._log_btn.configure(
                text="■  Stop logging",
                fg_color=RED_PRIMARY, hover_color="#791F1F",
                text_color="#FCEBEB",
            )
        else:
            self._log_btn.configure(
                text="▶  Start logging",
                fg_color=GREEN_PRIMARY, hover_color="#27500A",
                text_color=GREEN_LIGHT,
            )

    def update(self, conns_info, stats):
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

        self._s_tags.set(total_tags, BLUE_PRIMARY)
        interval_display = f"{stats.get('interval_ms', 1000)/1000:.2f} s" if stats.get("interval_ms") else "—"
        self._s_interval.set(interval_display)
        self._s_rows.set(f"{stats.get('total_rows', 0):,}")
        self._s_errors.set(
            str(errors),
            color=RED_PRIMARY if errors else ("gray10", "gray90"),
        )
        self._update_lbl.configure(text="Live")

        if stats.get("running"):
            fname = stats.get("shared_filename") or ""
            rows  = stats.get("total_rows", 0)
            self._csv_name.configure(text=fname or "Per-connection files")
            self._csv_info.configure(
                text=f"Started {stats.get('start_time','')} · {rows:,} rows total")
        else:
            self._csv_name.configure(text="—")
            self._csv_info.configure(text="Not logging")

        self._draw_trend()

    def _on_sel(self, _event):
        sel = self._tree.selection()
        if sel:
            vals = self._tree.item(sel[0])["values"]
            self._sel_tag_key = None
            tag_name = vals[0]
            conn_name = vals[3]
            # find key
            for k in self._trend_data:
                if tag_name in k:
                    self._sel_tag_key = k
                    break
            self._trend_title.configure(text=f"Trend — {tag_name}")

    def _draw_trend(self):
        if not HAS_MPL or not self._sel_tag_key:
            return
        data = list(self._trend_data.get(self._sel_tag_key, []))
        if len(data) < 2:
            return
        self._ax.clear()
        self._ax.plot(data, color=BLUE_PRIMARY, linewidth=1.5)
        self._ax.fill_between(range(len(data)), data, alpha=0.08, color=BLUE_PRIMARY)
        self._ax.set_facecolor("#F8F8F6")
        self._ax.tick_params(labelsize=8)
        self._ax.spines["top"].set_visible(False)
        self._ax.spines["right"].set_visible(False)
        self._ax.set_xlabel("Samples", fontsize=8)
        self._fig.tight_layout(pad=1.0)
        self._canvas.draw()
