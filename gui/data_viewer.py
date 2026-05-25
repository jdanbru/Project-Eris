"""
gui/data_viewer.py
──────────────────
Project Eris v4.3 – Data Viewer screen.

Allows the user to open any eris_*.csv and analyse historical data.

Features:
  - File picker (Open CSV file button)
  - Per-tag checkboxes with colour swatches — show/hide individual traces
  - Select All / None shortcuts
  - Multi-trace line chart with legend
  - Hover tooltip: snaps to nearest sample, shows tag + value + timestamp
  - Zoom: scroll wheel zooms in/out on X axis
  - Pan: click and drag left/right to scroll along X axis
  - Toolbar buttons: Reset zoom, Zoom In, Zoom Out
  - X axis label: "Cycle Number"
  - Y axis label: "Recorded Value"
"""

import csv
import customtkinter as ctk
from tkinter import filedialog
from pathlib import Path

try:
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

from gui.theme import BLUE_PRIMARY, text_muted
from gui.widgets import Card, GhostBtn

# Up to 10 simultaneous traces — readable on white background
TRACE_COLORS = [
    "#1A6FC4",   # blue
    "#E05C2A",   # orange
    "#2E9E4F",   # green
    "#9B3EC8",   # purple
    "#C8A800",   # gold
    "#17A0B8",   # teal
    "#D63B3B",   # red
    "#5A7A8E",   # steel
    "#8E44AD",   # violet
    "#7D5A50",   # brown
]

# How many samples to show at once at default zoom
DEFAULT_VIEW_SAMPLES = 200


class DataViewerScreen(ctk.CTkFrame):
    """
    Full-screen data analysis panel.

    Left panel  : tag checkbox list (show/hide per tag)
    Right panel : matplotlib chart with hover, zoom, and pan
    """

    def __init__(self, parent):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self._csv_path    = None
        self._tag_names   = []        # ordered list of column names (excl. timestamp)
        self._tag_units   = {}        # { tag: unit_string }  (from row-2 unit header)
        self._tag_data    = {}        # { tag: [float_or_None, ...] }
        self._timestamps  = []        # parallel list of timestamp strings
        self._check_vars  = {}        # { tag: BooleanVar }
        self._lines       = {}        # { tag: Line2D }
        self._annot       = None      # hover annotation
        self._vline       = None      # hover vertical indicator
        self._drag_start  = None      # x data coord where pan drag began
        self._x_min       = 0.0      # current view window left edge
        self._x_max       = float(DEFAULT_VIEW_SAMPLES)  # current view window right edge
        self._build()

    # ── build ─────────────────────────────────────────────────────────────

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── topbar ────────────────────────────────────────────────────────
        tb = ctk.CTkFrame(self, corner_radius=0,
                          fg_color="white",
                          border_width=1, border_color="gray85")
        tb.grid(row=0, column=0, sticky="ew")
        tb.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(tb, text="Data Viewer",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, padx=14, pady=10, sticky="w")

        GhostBtn(tb, text="📂  Open CSV file", width=145,
                 command=self._open_file).grid(
            row=0, column=1, padx=6, pady=8, sticky="w")

        # Zoom/pan toolbar buttons
        zoom_frame = ctk.CTkFrame(tb, fg_color="transparent")
        zoom_frame.grid(row=0, column=2, padx=6, pady=8, sticky="w")
        GhostBtn(zoom_frame, text="↺  Reset zoom", width=110, height=28,
                 command=self._reset_zoom).pack(side="left", padx=2)
        GhostBtn(zoom_frame, text="🔍+", width=50, height=28,
                 command=self._zoom_in).pack(side="left", padx=2)
        GhostBtn(zoom_frame, text="🔍−", width=50, height=28,
                 command=self._zoom_out).pack(side="left", padx=2)

        self._file_lbl = ctk.CTkLabel(tb,
                                       text="No file open — click 'Open CSV file' to begin",
                                       font=ctk.CTkFont(size=11),
                                       text_color=text_muted(), anchor="w")
        self._file_lbl.grid(row=0, column=3, padx=6, pady=8, sticky="w")

        # ── body ──────────────────────────────────────────────────────────
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=8)
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=0)   # tag list — fixed
        body.grid_columnconfigure(1, weight=1)   # chart — fills space

        # ── left: tag list ────────────────────────────────────────────────
        tag_panel = Card(body)
        tag_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        tag_panel.grid_rowconfigure(2, weight=1)
        tag_panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(tag_panel, text="Tags",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     anchor="w").grid(row=0, column=0, sticky="w",
                                      padx=12, pady=(10, 4))

        btn_row = ctk.CTkFrame(tag_panel, fg_color="transparent")
        btn_row.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 4))
        GhostBtn(btn_row, text="All",  width=50, height=24,
                 command=self._select_all).pack(side="left", padx=2)
        GhostBtn(btn_row, text="None", width=50, height=24,
                 command=self._select_none).pack(side="left", padx=2)

        self._tag_list = ctk.CTkScrollableFrame(
            tag_panel, width=190, fg_color="transparent", corner_radius=0)
        self._tag_list.grid(row=2, column=0, sticky="nsew", padx=4, pady=(0, 8))
        self._tag_list.grid_columnconfigure(0, weight=1)

        self._no_file_lbl = ctk.CTkLabel(
            self._tag_list,
            text="Open a CSV\nfile to see tags",
            font=ctk.CTkFont(size=11),
            text_color=text_muted())
        self._no_file_lbl.grid(row=0, column=0, pady=20)

        # ── right: chart ──────────────────────────────────────────────────
        chart_panel = Card(body)
        chart_panel.grid(row=0, column=1, sticky="nsew")
        chart_panel.grid_rowconfigure(0, weight=1)
        chart_panel.grid_columnconfigure(0, weight=1)

        if HAS_MPL:
            self._fig  = Figure(figsize=(8, 5), dpi=100)
            self._ax   = self._fig.add_subplot(111)
            self._fig.patch.set_facecolor("#F8F8F6")
            self._ax.set_facecolor("#F8F8F6")
            self._ax.spines["top"].set_visible(False)
            self._ax.spines["right"].set_visible(False)
            self._ax.set_xlabel("Cycle Number", fontsize=10)
            self._ax.set_ylabel("Recorded Value", fontsize=10)
            self._ax.grid(True, color="#E8E8E8", linewidth=0.5, alpha=0.8)
            self._fig.tight_layout(pad=1.8)

            self._canvas = FigureCanvasTkAgg(self._fig, master=chart_panel)
            self._canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew",
                                               padx=4, pady=4)

            # ── connect interactive events ─────────────────────────────
            # Hover tooltip
            self._fig.canvas.mpl_connect("motion_notify_event", self._on_hover)
            # Scroll wheel zoom
            self._fig.canvas.mpl_connect("scroll_event",        self._on_scroll)
            # Click-and-drag pan
            self._fig.canvas.mpl_connect("button_press_event",  self._on_drag_start)
            self._fig.canvas.mpl_connect("button_release_event", self._on_drag_end)
            self._fig.canvas.mpl_connect("motion_notify_event", self._on_drag_move)

            self._draw_empty_state()
        else:
            ctk.CTkLabel(chart_panel,
                         text="matplotlib is required.\nRun: pip install matplotlib",
                         font=ctk.CTkFont(size=13),
                         text_color=text_muted()).grid(row=0, column=0, pady=60)

    # ── file loading ──────────────────────────────────────────────────────

    def _open_file(self):
        path = filedialog.askopenfilename(
            title="Open CSV log file",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if path:
            self._load_csv(Path(path))

    def _load_csv(self, path: Path):
        """
        Parse CSV.  Supports both single-header and two-header (unit row) formats.

        Single header:  row 0 = column names, row 1+ = data
        Unit header:    row 0 = column names, row 1 = units (first cell blank), row 2+ = data
        """
        self._csv_path   = path
        self._tag_names  = []
        self._tag_units  = {}
        self._tag_data   = {}
        self._timestamps = []

        try:
            with open(path, newline="", encoding="utf-8-sig") as f:
                rows = list(csv.reader(f))

            if len(rows) < 2:
                self._file_lbl.configure(text="File is empty.")
                return

            headers = rows[0]

            # Detect optional unit row (second row with blank timestamp cell)
            if len(rows) > 1 and rows[1][0].strip() == "":
                unit_row  = rows[1]
                data_rows = rows[2:]
            else:
                unit_row  = []
                data_rows = rows[1:]

            # Build tag name list (skip timestamp column 0)
            self._tag_names = [h.strip() for h in headers[1:] if h.strip()]

            for i, tag in enumerate(self._tag_names, start=1):
                self._tag_units[tag] = (unit_row[i].strip()
                                         if i < len(unit_row) else "")
                self._tag_data[tag]  = []

            for row in data_rows:
                if not row:
                    continue
                self._timestamps.append(row[0])
                for i, tag in enumerate(self._tag_names, start=1):
                    raw = row[i].strip() if i < len(row) else ""
                    try:
                        self._tag_data[tag].append(float(raw))
                    except (ValueError, TypeError):
                        self._tag_data[tag].append(None)

            n_tags = len(self._tag_names)
            n_rows = len(data_rows)
            self._file_lbl.configure(
                text=f"{path.name}  ·  {n_tags} tag{'s' if n_tags != 1 else ''}  ·  {n_rows:,} rows")

            # Reset zoom to show first DEFAULT_VIEW_SAMPLES samples
            total = len(data_rows)
            self._x_min = 0.0
            self._x_max = float(min(DEFAULT_VIEW_SAMPLES, total))

            self._build_tag_checkboxes()
            self._replot()

        except Exception as e:
            self._file_lbl.configure(text=f"Error loading file: {e}")

    # ── tag checkbox list ─────────────────────────────────────────────────

    def _build_tag_checkboxes(self):
        """Rebuild the left-panel checkbox list from loaded tag names."""
        for w in self._tag_list.winfo_children():
            w.destroy()
        self._check_vars = {}

        if not self._tag_names:
            ctk.CTkLabel(self._tag_list, text="No tags found",
                         font=ctk.CTkFont(size=11),
                         text_color=text_muted()).grid(row=0, column=0, pady=10)
            return

        for i, tag in enumerate(self._tag_names):
            var   = ctk.BooleanVar(value=True)
            self._check_vars[tag] = var
            color = TRACE_COLORS[i % len(TRACE_COLORS)]
            unit  = self._tag_units.get(tag, "")
            label = tag + (f"  [{unit}]" if unit else "")

            row_f = ctk.CTkFrame(self._tag_list, fg_color="transparent")
            row_f.grid(row=i, column=0, sticky="ew", pady=1)
            row_f.grid_columnconfigure(1, weight=1)

            # Colour swatch matching the trace colour
            ctk.CTkLabel(row_f, text="━",
                         font=ctk.CTkFont(size=14),
                         text_color=color, width=22).grid(
                row=0, column=0, padx=(2, 4))

            ctk.CTkCheckBox(
                row_f,
                text=label,
                variable=var,
                font=ctk.CTkFont(size=11),
                command=self._replot,
            ).grid(row=0, column=1, sticky="w")

    def _select_all(self):
        for v in self._check_vars.values():
            v.set(True)
        self._replot()

    def _select_none(self):
        for v in self._check_vars.values():
            v.set(False)
        self._replot()

    # ── plotting ──────────────────────────────────────────────────────────

    def _draw_empty_state(self):
        """Placeholder shown before any file is loaded."""
        self._ax.clear()
        self._ax.text(0.5, 0.5, "Open a CSV file to plot tag data",
                      ha="center", va="center",
                      transform=self._ax.transAxes,
                      fontsize=13, color="#888888")
        self._ax.set_xticks([])
        self._ax.set_yticks([])
        self._canvas.draw()

    def _replot(self):
        """Redraw chart with currently visible tags, preserving zoom window."""
        if not HAS_MPL or not self._tag_names:
            return

        self._ax.clear()
        self._lines  = {}
        self._annot  = None
        self._vline  = None

        visible = [t for t in self._tag_names
                   if self._check_vars.get(t, ctk.BooleanVar(value=True)).get()]

        if not visible:
            self._ax.text(0.5, 0.5, "No tags selected — tick a checkbox to plot",
                          ha="center", va="center",
                          transform=self._ax.transAxes,
                          fontsize=12, color="#888888")
            self._canvas.draw()
            return

        for tag in visible:
            color = TRACE_COLORS[self._tag_names.index(tag) % len(TRACE_COLORS)]
            data  = self._tag_data.get(tag, [])
            xs    = [i for i, v in enumerate(data) if v is not None]
            ys    = [v for v in data if v is not None]
            if not xs:
                continue
            unit  = self._tag_units.get(tag, "")
            label = tag + (f" [{unit}]" if unit else "")
            line, = self._ax.plot(xs, ys,
                                   color=color, linewidth=1.5,
                                   label=label,
                                   marker="o", markersize=2.5,
                                   markerfacecolor=color,
                                   markeredgewidth=0,
                                   picker=5)
            self._lines[tag] = line

        if self._lines:
            leg = self._ax.legend(loc="upper left", fontsize=8,
                                   framealpha=0.9,
                                   facecolor="white", edgecolor="#CCCCCC")

        # Hover annotation (hidden until mouse moves in)
        self._annot = self._ax.annotate(
            "", xy=(0, 0), xytext=(14, 14),
            textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.4",
                      fc="white", ec=BLUE_PRIMARY, lw=1, alpha=0.93),
            fontsize=9, visible=False)

        # Vertical hover indicator
        self._vline = self._ax.axvline(
            x=0, color=BLUE_PRIMARY, linewidth=0.9,
            linestyle="--", visible=False, alpha=0.4)

        # Restore zoom window
        self._ax.set_xlim(self._x_min, self._x_max)

        self._ax.set_facecolor("#F8F8F6")
        self._ax.tick_params(labelsize=8)
        self._ax.spines["top"].set_visible(False)
        self._ax.spines["right"].set_visible(False)
        self._ax.set_xlabel("Cycle Number", fontsize=10)
        self._ax.set_ylabel("Recorded Value", fontsize=10)
        self._ax.grid(True, color="#E8E8E8", linewidth=0.5, alpha=0.8)
        self._fig.tight_layout(pad=1.8)
        self._canvas.draw()

    # ── zoom & pan ────────────────────────────────────────────────────────

    def _apply_xlim(self):
        """Apply the current _x_min/_x_max window to the axes and redraw."""
        if not self._tag_data:
            return
        # Clamp to data bounds
        total = max(
            (len(d) for d in self._tag_data.values()), default=1
        )
        span  = self._x_max - self._x_min
        # Don't allow zooming in smaller than 10 samples
        if span < 10:
            span = 10
        # Don't allow scrolling past data
        self._x_min = max(0.0, self._x_min)
        self._x_max = self._x_min + span
        if self._x_max > total:
            self._x_max = float(total)
            self._x_min = max(0.0, self._x_max - span)
        self._ax.set_xlim(self._x_min, self._x_max)
        self._canvas.draw_idle()

    def _on_scroll(self, event):
        """Scroll wheel: zoom in (up) / zoom out (down) centred on cursor."""
        if event.inaxes != self._ax:
            return
        zoom_factor = 0.85 if event.button == "up" else 1.0 / 0.85
        x_cursor    = event.xdata if event.xdata is not None else \
                      (self._x_min + self._x_max) / 2
        span        = self._x_max - self._x_min
        new_span    = span * zoom_factor
        # Keep cursor position stable
        ratio       = (x_cursor - self._x_min) / span if span else 0.5
        self._x_min = x_cursor - ratio * new_span
        self._x_max = x_cursor + (1 - ratio) * new_span
        self._apply_xlim()

    def _zoom_in(self):
        """Toolbar Zoom In button — zoom to centre."""
        mid = (self._x_min + self._x_max) / 2
        half_span = (self._x_max - self._x_min) / 2 * 0.7
        self._x_min = mid - half_span
        self._x_max = mid + half_span
        self._apply_xlim()

    def _zoom_out(self):
        """Toolbar Zoom Out button."""
        mid = (self._x_min + self._x_max) / 2
        half_span = (self._x_max - self._x_min) / 2 * (1 / 0.7)
        self._x_min = mid - half_span
        self._x_max = mid + half_span
        self._apply_xlim()

    def _reset_zoom(self):
        """Reset to show all data."""
        if not self._tag_data:
            return
        total = max((len(d) for d in self._tag_data.values()), default=1)
        self._x_min = 0.0
        self._x_max = float(total)
        self._apply_xlim()

    def _on_drag_start(self, event):
        """Record start point for click-and-drag pan."""
        if event.inaxes == self._ax and event.button == 1:
            self._drag_start = event.xdata

    def _on_drag_end(self, event):
        """Clear drag state on mouse release."""
        self._drag_start = None

    def _on_drag_move(self, event):
        """Pan the view left/right as the user drags."""
        if (self._drag_start is None or
                event.inaxes != self._ax or
                event.xdata is None):
            return
        if event.button != 1:
            return
        delta = self._drag_start - event.xdata
        self._x_min += delta
        self._x_max += delta
        # Don't update _drag_start so drag feels natural
        self._apply_xlim()

    # ── hover tooltip ─────────────────────────────────────────────────────

    def _on_hover(self, event):
        """
        Show a tooltip with the nearest tag's value and timestamp.
        Snaps to the nearest sample index across all visible traces.
        """
        if not HAS_MPL or self._annot is None:
            return

        if event.inaxes != self._ax:
            if self._annot.get_visible():
                self._annot.set_visible(False)
                if self._vline:
                    self._vline.set_visible(False)
                self._canvas.draw_idle()
            return

        x_cursor = event.xdata
        if x_cursor is None:
            return

        # Find the nearest data point across all visible lines
        best_tag  = None
        best_x    = None
        best_y    = None
        best_dist = float("inf")

        for tag, line in self._lines.items():
            data = self._tag_data.get(tag, [])
            xs   = [i for i, v in enumerate(data) if v is not None]
            if not xs:
                continue
            nx   = min(xs, key=lambda x: abs(x - x_cursor))
            dist = abs(nx - x_cursor)
            if dist < best_dist:
                best_dist = dist
                best_tag  = tag
                best_x    = nx
                best_y    = data[nx]

        if best_tag is None or best_y is None:
            return

        ts   = self._timestamps[best_x] if best_x < len(self._timestamps) else ""
        unit = self._tag_units.get(best_tag, "")
        unit_str = f" {unit}" if unit else ""

        self._annot.xy = (best_x, best_y)
        self._annot.set_text(
            f"{best_tag}\n{best_y:g}{unit_str}\n{ts}")
        self._annot.set_visible(True)

        if self._vline:
            self._vline.set_xdata([best_x, best_x])
            self._vline.set_visible(True)

        self._canvas.draw_idle()
