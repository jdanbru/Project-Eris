"""
gui/app.py
──────────
Project Eris – root application window.

The App class is the top-level CustomTkinter window.  It owns:
  - The config dict (loaded from disk, saved on changes)
  - The ConnectionManager (all PLC connections)
  - The CSVLogger (all logging threads)
  - The Sidebar (navigation + connection list)
  - All screen widgets (Dashboard, Connections, CSV, Diagnostics, Help, Settings)

App is responsible for:
  - Wiring up every callback between the sidebar, screens, and backend
  - Switching between screens when the user navigates
  - Polling the PLCs every 800 ms to refresh the dashboard while logging
  - Saving config to disk whenever settings or connections change
  - Cleaning up (stopping logger, disconnecting PLCs) on window close

Nothing in this file communicates directly with PLCs or writes to CSV —
all of that is delegated to the plc/ and logger/ modules.
"""

import uuid
import threading
import customtkinter as ctk
from tkinter import messagebox

from config import load_config, save_config
from plc import ConnectionManager, STATUS_CONNECTED
from logger import CSVLogger
from gui.sidebar import Sidebar
from gui.dashboard import DashboardScreen
from gui.connections import ConnectionsScreen
from gui.csv_screen import CSVScreen
from gui.diagnostics import DiagnosticsScreen
from gui.help_screen import HelpScreen
from gui.data_viewer import DataViewerScreen
from gui.settings_screen import SettingsScreen


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Project Eris")
        self.geometry("1020x660")
        self.minsize(880, 580)

        self._cfg = load_config()
        ctk.set_appearance_mode("light")   # dark mode removed in v4.3

        self._cm = ConnectionManager(on_status_change=self._on_status)
        self._logger = CSVLogger(self._cfg, self._cm,
                                  on_stats_update=self._on_stats)
        self._poll_job    = None
        self._active_conn = None          # selected connection ID

        self._build_ui()
        self._load_connections()

        if self._cfg.get("auto_connect"):
            self.after(600, self._cm.connect_all)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI construction ───────────────────────────────────────────────────
    def _build_ui(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.sidebar = Sidebar(
            self,
            on_nav=self._show,
            on_conn_select=self._sel_conn,
            on_add_conn=self._add_conn,
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        main = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(0, weight=1)
        self._main = main

        self._dash  = DashboardScreen(main,
                                       on_toggle_log=self._toggle_log,
                                       on_connect=self._connect_all)
        self._data_viewer = DataViewerScreen(main)
        self._conns = ConnectionsScreen(main,
                                         on_save=self._save_conn,
                                         on_delete=self._del_conn,
                                         on_test=self._test_conn)
        self._csv   = CSVScreen(main, self._cfg)
        self._diag  = DiagnosticsScreen(main, get_conn_manager=lambda: self._cm)
        self._help  = HelpScreen(main)
        self._sett  = SettingsScreen(main, self._cfg, on_save=self._save_settings)

        self._screens = {
            "dashboard":   self._dash,
            "data_viewer": self._data_viewer,
            "connections": self._conns,
            "csv":         self._csv,
            "diagnostics": self._diag,
            "help":        self._help,
            "settings":    self._sett,
        }
        self._cur_screen = None
        self._show("dashboard")

    def _show(self, name):
        if self._cur_screen:
            self._cur_screen.grid_forget()
        s = self._screens[name]
        s.grid(row=0, column=0, sticky="nsew")
        self._cur_screen = s
        self.sidebar.set_active(name)

        if name == "csv":
            self._csv.refresh(self._cfg, self._cm)
        elif name == "diagnostics":
            self._diag.refresh_all()
        elif name == "dashboard":
            self._refresh_dash()

    # ── connections ───────────────────────────────────────────────────────
    def _load_connections(self):
        for cfg in self._cfg.get("connections", []):
            self._cm.add_connection(cfg)
        self._refresh_sidebar()

    def _refresh_sidebar(self):
        conns = []
        for cfg in self._cfg.get("connections", []):
            plc = self._cm.get_connection(cfg["id"])
            conns.append({
                "cfg":    cfg,
                "status": plc.status if plc else "disconnected",
                "active": cfg["id"] == self._active_conn,
            })
        self.sidebar.update_connections(conns)

    def _sel_conn(self, cid):
        self._active_conn = cid
        cfg = next((c for c in self._cfg.get("connections", []) if c["id"] == cid), None)
        if cfg:
            self._show("connections")
            self._conns.load_connection(cfg)
        self._refresh_sidebar()

    def _add_conn(self):
        self._active_conn = None
        self._show("connections")
        self._conns.load_connection(None)

    def _save_conn(self, cfg):
        if not cfg.get("id"):
            cfg["id"] = str(uuid.uuid4())
        conns = self._cfg.get("connections", [])
        idx   = next((i for i, c in enumerate(conns) if c["id"] == cfg["id"]), None)
        if idx is not None:
            conns[idx] = cfg
        else:
            conns.append(cfg)
        self._cfg["connections"] = conns
        save_config(self._cfg)
        self._cm.add_connection(cfg)
        self._active_conn = cfg["id"]
        self._refresh_sidebar()
        messagebox.showinfo("Saved", f"'{cfg['name']}' saved.")

    def _del_conn(self, cid):
        self._cfg["connections"] = [
            c for c in self._cfg.get("connections", []) if c["id"] != cid
        ]
        save_config(self._cfg)
        self._cm.remove_connection(cid)
        self._active_conn = None
        self._refresh_sidebar()
        self._conns.load_connection(None)

    def _test_conn(self, cfg):
        from plc.connection import PLCConnection, STATUS_CONNECTED
        def _do():
            tmp = PLCConnection(cfg)
            tmp._try_connect()
            if tmp.status == STATUS_CONNECTED:
                tmp.disconnect()
                self.after(0, lambda: messagebox.showinfo(
                    "Success", f"Connected to {cfg['ip']} successfully!"))
            else:
                self.after(0, lambda: messagebox.showerror(
                    "Failed", f"Could not connect:\n{tmp.error_msg}"))
        threading.Thread(target=_do, daemon=True).start()

    # ── logging ───────────────────────────────────────────────────────────
    def _toggle_log(self):
        if self._logger.is_running:
            self._logger.stop()
            self._dash.set_logging(False)
            self._stop_poll()
        else:
            self._logger.start()
            self._dash.set_logging(True)
            self._start_poll()

    def _connect_all(self):
        threading.Thread(target=self._cm.connect_all, daemon=True).start()

    def _start_poll(self):
        self._poll_job = self.after(800, self._poll)

    def _stop_poll(self):
        if self._poll_job:
            self.after_cancel(self._poll_job)
            self._poll_job = None

    def _poll(self):
        self._refresh_dash()
        self._poll_job = self.after(800, self._poll)

    def _refresh_dash(self):
        all_vals = self._cm.read_all()
        conns_info = []
        for cfg in self._cfg.get("connections", []):
            plc = self._cm.get_connection(cfg["id"])
            if plc:
                conns_info.append({
                    "id":       plc.id,
                    "name":     plc.name,
                    "plc_type": plc.plc_type,
                    "status":   plc.status,
                    "log_mode": plc.log_mode,
                    "tags":     plc.tags,
                    "values":   all_vals.get(plc.id, {}),
                })
        stats = self._logger.get_stats()
        # grab first shared filename for display
        shared_fn = ""
        if stats.get("shared_path"):
            from pathlib import Path as _P
            shared_fn = _P(stats["shared_path"]).name
        stats["shared_filename"] = shared_fn
        stats["interval_ms"] = self._cfg.get("log_interval", 1.0) * 1000

        self._dash.update(conns_info, stats)
        self._refresh_sidebar()

    # ── callbacks ─────────────────────────────────────────────────────────
    def _on_status(self, conn_id, status, msg):
        self.after(0, self._refresh_sidebar)

    def _on_stats(self):
        pass

    # ── settings ──────────────────────────────────────────────────────────
    def _save_settings(self, new_cfg):
        self._cfg.update(new_cfg)
        self._logger.config = self._cfg
        save_config(self._cfg)
        messagebox.showinfo("Saved", "Settings saved.")


    # ── close ─────────────────────────────────────────────────────────────
    def _on_close(self):
        if self._logger.is_running:
            self._logger.stop()
        self._cm.disconnect_all()
        self.destroy()
