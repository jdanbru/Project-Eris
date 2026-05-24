"""
logger/csv_logger.py
────────────────────
Project Eris – CSV logging engine.

This module handles all CSV file creation and writing.  It supports two
logging modes per connection:

  Interval mode  – writes one row every N milliseconds
  Trigger mode   – writes one row each time a BOOL tag transitions False→True

It also supports two CSV file strategies:

  Shared CSV  – all connections whose "separate_csv" flag is False are
                written into one combined file, with one column per tag.
  Separate CSV – connections with "separate_csv" = True get their own
                 dedicated file (and sub-folder) so their data stays isolated.

A new file (or set of files) is created every time the user clicks
"Start logging".  Files are never appended to.

Key classes:
  ConnectionLogger  – writes one connection's data (to shared or own file)
  CSVLogger         – orchestrates all ConnectionLogger instances
"""

import csv
import threading
import time
from datetime import datetime
from pathlib import Path

from config import get_logs_dir, _safe_name


# ── ConnectionLogger ──────────────────────────────────────────────────────

class ConnectionLogger:
    """
    Handles CSV writing for a single PLC connection.

    If the connection has separate_csv = True, this class opens and owns
    its own CSV file.  Otherwise it writes to the shared writer/lock that
    CSVLogger passes in at construction time.
    """

    def __init__(self, conn, config: dict,
                 shared_writer=None, shared_lock: threading.Lock = None):
        """
        Parameters
        ----------
        conn         : PLCConnection  – the connection this logger serves
        config       : dict           – app config (for csv_folder, timestamp_format)
        shared_writer: csv.writer     – the shared file writer (None if using own file)
        shared_lock  : threading.Lock – protects shared_writer from concurrent access
        """
        self.conn           = conn
        self.config         = config
        self._shared_writer = shared_writer
        self._shared_lock   = shared_lock

        # File handles used when separate_csv = True
        self._file     = None
        self._writer   = None
        self._lock     = threading.Lock()   # protects this connection's own file
        self._filepath = None
        self._rows     = 0                  # running row count (displayed in dashboard)
        self._start_ts = None

        # Open the connection's own file immediately if separate CSV is requested
        if conn.separate_csv:
            self._open_file()

    def _open_file(self) -> None:
        """
        Create and open a new CSV file for this connection.

        File path: <csv_folder>/<SafeConnectionName>/eris_<Name>_<timestamp>.csv
        The header row is written immediately on open.
        """
        folder    = get_logs_dir(self.config, self.conn.name)
        ts        = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename  = f"eris_{_safe_name(self.conn.name)}_{ts}.csv"
        self._filepath = folder / filename
        self._start_ts = datetime.now()

        # Build the header: one column per enabled tag
        enabled_tags = [t for t in self.conn.tags if t.get("enabled", True)]
        headers = ["timestamp"] + [t["address"] for t in enabled_tags]

        self._file   = open(self._filepath, "w", newline="")
        self._writer = csv.writer(self._file)
        self._writer.writerow(headers)
        self._file.flush()

    def write_row(self, values: dict, ts_str: str) -> None:
        """
        Write one data row.

        Parameters
        ----------
        values : dict  – { "TagAddress": value_or_None, ... } from PLC read
        ts_str : str   – pre-formatted timestamp string
        """
        # Build the row: timestamp first, then one value per enabled tag.
        # None values become empty strings in the CSV.
        row = [ts_str] + [
            ("" if values.get(t["address"]) is None else values[t["address"]])
            for t in self.conn.tags
            if t.get("enabled", True)
        ]

        if self.conn.separate_csv and self._writer:
            # Write to this connection's own file
            with self._lock:
                self._writer.writerow(row)
                self._rows += 1
                # Flush to disk every 10 rows to reduce data loss on crash
                if self._rows % 10 == 0:
                    self._file.flush()

        elif self._shared_writer and self._shared_lock:
            # Write to the shared file (lock prevents garbled rows from
            # two connections writing simultaneously)
            with self._shared_lock:
                self._shared_writer.writerow(row)
                self._rows += 1

    def close(self) -> None:
        """Flush and close the connection's own CSV file (if open)."""
        try:
            if self._file:
                self._file.flush()
                self._file.close()
        except Exception:
            pass

    @property
    def filepath(self) -> "Path | None":
        """Path to this connection's own CSV file, or None if using shared."""
        return self._filepath

    @property
    def row_count(self) -> int:
        """Number of data rows written so far this session."""
        return self._rows

    def file_size(self) -> int:
        """Current file size in bytes (0 if file does not exist yet)."""
        if self._filepath and Path(self._filepath).exists():
            return Path(self._filepath).stat().st_size
        return 0


# ── CSVLogger ─────────────────────────────────────────────────────────────

class CSVLogger:
    """
    Orchestrates logging across all PLC connections.

    One background thread is created per connection.  Each thread runs its
    own polling loop at the connection's configured interval, completely
    independently of the other connections.
    """

    def __init__(self, config: dict, connection_manager, on_stats_update=None):
        """
        Parameters
        ----------
        config             : dict  – app config
        connection_manager : ConnectionManager
        on_stats_update    : callable, optional
            Called after each row is written so the dashboard can refresh
            the row count and file size without polling on its own.
        """
        self.config            = config
        self.conn_manager      = connection_manager
        self.on_stats_update   = on_stats_update

        self._running       = False
        self._conn_loggers  = {}           # { conn_id: ConnectionLogger }
        self._threads       = []           # all logging threads

        # Shared file state (used by connections that don't have separate_csv)
        self._shared_file   = None
        self._shared_writer = None
        self._shared_lock   = threading.Lock()
        self._shared_path   = None

        self._start_ts = None

    @property
    def is_running(self) -> bool:
        """True if logging is currently active."""
        return self._running

    # ── start / stop ──────────────────────────────────────────────────────

    def start(self) -> None:
        """
        Begin logging all connections.

        Opens the shared CSV file (if needed), creates a ConnectionLogger
        for each connection, and starts a background thread for each.
        Does nothing if logging is already running.
        """
        if self._running:
            return

        self._running  = True
        self._start_ts = datetime.now()
        self._conn_loggers = {}
        self._threads      = []

        # Open the shared file only if at least one connection uses it
        shared_needed = any(
            not c.separate_csv
            for c in self.conn_manager.connections.values()
        )
        if shared_needed:
            self._open_shared_file()

        # Create one ConnectionLogger and one thread per connection
        for conn in self.conn_manager.connections.values():
            cl = ConnectionLogger(
                conn, self.config,
                shared_writer=self._shared_writer,
                shared_lock=self._shared_lock,
            )
            self._conn_loggers[conn.id] = cl

            t = threading.Thread(
                target=self._log_loop,
                args=(conn, cl),
                daemon=True,
                name=f"logger-{conn.name}",
            )
            self._threads.append(t)
            t.start()

    def _open_shared_file(self) -> None:
        """
        Create and open the shared CSV file.

        The header is built from all enabled tags across all connections
        that do NOT have separate_csv set.  Each column is labelled
        "ConnectionName::TagAddress" to make it clear which PLC the value
        came from.
        """
        folder   = get_logs_dir(self.config)
        ts       = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"eris_{ts}.csv"
        self._shared_path  = folder / filename
        self._shared_file  = open(self._shared_path, "w", newline="")
        self._shared_writer = csv.writer(self._shared_file)

        # Header: timestamp + one column per enabled tag for each shared connection
        headers = ["timestamp"]
        for conn in self.conn_manager.connections.values():
            if not conn.separate_csv:
                for tag in conn.tags:
                    if tag.get("enabled", True):
                        headers.append(f"{conn.name}::{tag['address']}")

        self._shared_writer.writerow(headers)
        self._shared_file.flush()

    def stop(self) -> None:
        """
        Stop all logging threads and close all open CSV files.

        Waits up to 3 seconds for each thread to finish its current write
        before closing the files.
        """
        self._running = False

        for t in self._threads:
            t.join(timeout=3)

        # Close all per-connection files
        for cl in self._conn_loggers.values():
            cl.close()

        # Close the shared file
        try:
            if self._shared_file:
                self._shared_file.flush()
                self._shared_file.close()
        except Exception:
            pass

        self._shared_file   = None
        self._shared_writer = None

    # ── logging loop ──────────────────────────────────────────────────────

    def _log_loop(self, conn, cl: ConnectionLogger) -> None:
        """
        Per-connection logging loop.  Runs on its own daemon thread.

        Interval mode:  sleeps for conn.log_interval_ms between writes.
        Trigger mode:   polls the trigger tag every 50 ms and writes a row
                        only when a rising edge is detected.
        """
        interval_s = conn.log_interval_ms / 1000.0

        while self._running:
            t_start      = time.monotonic()
            should_write = False

            if conn.log_mode == "interval":
                # In interval mode, write a row whenever the PLC is connected
                should_write = (conn.status == "connected")
            else:
                # In trigger mode, check for a rising edge on the trigger tag
                should_write = conn.check_trigger()

            if should_write:
                ts_str = self._timestamp()
                values = conn.read_tags()
                try:
                    cl.write_row(values, ts_str)
                except Exception as e:
                    print(f"[Logger:{conn.name}] Write error: {e}")
                if self.on_stats_update:
                    self.on_stats_update()

            # Calculate how long to sleep before the next poll.
            # In trigger mode we always poll at 50 ms regardless of interval.
            elapsed  = time.monotonic() - t_start
            if conn.log_mode == "trigger":
                sleep_s = max(0, 0.05 - elapsed)
            else:
                sleep_s = max(0, interval_s - elapsed)

            time.sleep(sleep_s)

    def _timestamp(self) -> str:
        """
        Return the current time as a formatted string.

        "iso"   → 2026-05-24T08:31:00.123   (ISO 8601 with milliseconds)
        "excel" → 24/05/2026 08:31:00        (day/month/year for Excel)
        """
        fmt = self.config.get("timestamp_format", "iso")
        if fmt == "iso":
            return datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
        return datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    # ── stats ──────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """
        Return a summary dict used by the Dashboard to update its stat tiles.

        Keys:
            running       (bool)  – whether logging is active
            total_rows    (int)   – combined row count across all connections
            start_time    (str)   – HH:MM:SS when logging started
            connections   (dict)  – per-connection stats { conn_id: {...} }
            shared_path   (str)   – path to the shared CSV file (or "")
        """
        total_rows = sum(cl.row_count for cl in self._conn_loggers.values())

        conn_stats = {}
        for cid, cl in self._conn_loggers.items():
            conn_stats[cid] = {
                "rows":     cl.row_count,
                "filepath": str(cl.filepath) if cl.filepath else str(self._shared_path or ""),
                "filename": (cl.filepath.name if cl.filepath
                             else (self._shared_path.name if self._shared_path else "")),
                "size":     cl.file_size(),
            }

        return {
            "running":     self._running,
            "total_rows":  total_rows,
            "start_time":  self._start_ts.strftime("%H:%M:%S") if self._start_ts else "",
            "connections": conn_stats,
            "shared_path": str(self._shared_path) if self._shared_path else "",
        }

    def read_all(self) -> dict:
        """Convenience wrapper — reads all connected PLCs via the connection manager."""
        return self.conn_manager.read_all()


# ── file listing helper ───────────────────────────────────────────────────

def list_log_files(config: dict, conn_name: str = None) -> list:
    """
    Return a list of dicts describing CSV log files on disk.

    If conn_name is given, only files in that connection's sub-folder
    are returned.  Otherwise files in the base csv_folder are returned.

    Each dict has: name, path, size (bytes), modified (formatted string).
    Results are sorted newest-first.
    """
    base = Path(config.get("csv_folder",
                            str(Path.home() / "ProjectEris" / "Logs")))

    folder = base / _safe_name(conn_name) if conn_name else base

    if not folder.exists():
        return []

    files = sorted(folder.glob("eris_*.csv"), reverse=True)
    return [
        {
            "name":     f.name,
            "path":     str(f),
            "size":     f.stat().st_size,
            "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
        }
        for f in files
    ]
