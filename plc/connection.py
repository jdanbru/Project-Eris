"""
plc/connection.py
─────────────────
Project Eris – PLC communication layer.

This module handles everything related to talking to PLCs:
  - Connecting and disconnecting (Allen-Bradley via pylogix, Siemens via snap7)
  - Auto-retry when a connection drops during logging
  - Reading tag values for both AB and S7 data types
  - Trigger detection (rising-edge on a BOOL tag)
  - Diagnostics (device info, CPU state, firmware revision)

Key classes:
  PLCConnection      – Represents and manages one PLC connection
  ConnectionManager  – Holds all active PLCConnection instances

Connection status values (used throughout the GUI):
  STATUS_DISCONNECTED  – not yet connected or manually disconnected
  STATUS_CONNECTED     – actively communicating with the PLC
  STATUS_ERROR         – connection failed or was lost
  STATUS_RETRYING      – waiting before the next reconnect attempt
"""

import threading
import time
from datetime import datetime


# ── status constants ──────────────────────────────────────────────────────
# These string values are displayed in the sidebar and diagnostics screen.

STATUS_DISCONNECTED = "disconnected"
STATUS_CONNECTED    = "connected"
STATUS_ERROR        = "error"
STATUS_RETRYING     = "retrying"

# Minimum allowed logging interval in milliseconds.
# Enforced in the Connections screen UI and respected by the logger.
MIN_INTERVAL_MS = 100


# ── PLCConnection ─────────────────────────────────────────────────────────

class PLCConnection:
    """
    Manages the full lifecycle of one PLC connection.

    Responsibilities:
      - Store connection parameters (IP, slot, rack, tags, logging mode)
      - Connect and disconnect the underlying library client
      - Retry automatically in the background when the connection drops
      - Read all enabled tag values in a single call
      - Check for trigger tag rising edges (for trigger-mode logging)
      - Return diagnostic information about the device
    """

    def __init__(self, conn_cfg: dict, on_status_change=None):
        """
        Initialise from a connection config dict (as stored in config.json).

        Parameters
        ----------
        conn_cfg : dict
            Keys:  id, name, plc_type ("ab"|"s7"), ip, slot, rack,
                   tags, log_mode, log_interval_ms, trigger_tag, separate_csv
        on_status_change : callable, optional
            Called with (conn_id, status, error_msg) whenever the status changes.
            The GUI uses this to update the sidebar status dots in real time.
        """
        # ── identity ──────────────────────────────────────────────────────
        self.id       = conn_cfg["id"]
        self.name     = conn_cfg["name"]
        self.plc_type = conn_cfg["plc_type"]   # "ab" for Allen-Bradley, "s7" for Siemens
        self.ip       = conn_cfg["ip"]
        self.slot     = int(conn_cfg.get("slot", 0))
        self.rack     = int(conn_cfg.get("rack", 0))

        # ── tag list ──────────────────────────────────────────────────────
        # Each tag is a dict with keys: address, data_type, db_number,
        # offset, enabled.  See connections.py for the full schema.
        self.tags = conn_cfg.get("tags", [])

        # ── logging configuration ─────────────────────────────────────────
        # log_mode:        "interval" — log every N milliseconds
        #                  "trigger"  — log on rising edge of trigger_tag
        self.log_mode        = conn_cfg.get("log_mode", "interval")
        self.log_interval_ms = max(
            int(conn_cfg.get("log_interval_ms", 1000)),
            MIN_INTERVAL_MS,   # hard floor — never go below 100 ms
        )
        self.trigger_tag  = conn_cfg.get("trigger_tag", "")
        self.separate_csv = conn_cfg.get("separate_csv", False)

        # ── runtime state ─────────────────────────────────────────────────
        self.status    = STATUS_DISCONNECTED
        self.error_msg = ""
        self.on_status_change = on_status_change

        # The library client object (pylogix PLC() or snap7 Client()).
        # None when not connected.
        self._client = None

        # Threading helpers
        self._stop_event   = threading.Event()   # set to stop the retry loop
        self._retry_thread = None
        self._connected    = False

        # Previous value of the trigger tag — used to detect rising edges
        self._prev_trigger = False

    # ── status helper ──────────────────────────────────────────────────────

    def _set_status(self, status: str, msg: str = "") -> None:
        """Update internal status and notify the GUI callback if set."""
        self.status    = status
        self.error_msg = msg
        if self.on_status_change:
            self.on_status_change(self.id, status, msg)

    # ── connect / disconnect ───────────────────────────────────────────────

    def connect(self) -> None:
        """
        Attempt to connect to the PLC.  If the first attempt fails, start
        the background retry loop which keeps trying every 5 seconds until
        either the connection succeeds or disconnect() is called.

        This method is safe to call from a background thread (the app always
        does so to avoid freezing the GUI while connecting).
        """
        self._stop_event.clear()
        self._try_connect()
        if self.status != STATUS_CONNECTED:
            self._start_retry()

    def disconnect(self) -> None:
        """
        Cleanly shut down the connection and stop any running retry loop.
        Sets status to DISCONNECTED when complete.
        """
        # Signal the retry loop to stop if it is running
        self._stop_event.set()
        self._connected = False

        # Wait for the retry thread to exit gracefully (max 2 seconds)
        if self._retry_thread and self._retry_thread.is_alive():
            self._retry_thread.join(timeout=2)

        # Close the library client
        try:
            if self._client:
                if self.plc_type == "ab":
                    self._client.Close()
                else:
                    self._client.disconnect()
        except Exception:
            pass   # ignore errors on close — we're disconnecting anyway

        self._client = None
        self._set_status(STATUS_DISCONNECTED)

    def _try_connect(self) -> None:
        """
        Single connection attempt.  On success sets _connected = True and
        STATUS_CONNECTED.  On failure sets STATUS_ERROR with the error message.
        """
        try:
            if self.plc_type == "ab":
                self._connect_ab()
            else:
                self._connect_s7()

            self._connected = True
            self._set_status(STATUS_CONNECTED)

        except Exception as e:
            self._connected = False
            self._client    = None
            self._set_status(STATUS_ERROR, str(e))

    def _connect_ab(self) -> None:
        """
        Connect to an Allen-Bradley PLC using pylogix.

        A quick tag read is used to verify the connection is actually working,
        not just that the TCP socket opened.  If the PLC responds with a
        network-level failure (not just a missing tag) we raise an exception
        so the retry loop knows to keep trying.
        """
        from pylogix import PLC

        client = PLC()
        client.IPAddress     = self.ip
        client.ProcessorSlot = self.slot
        client.SocketTimeout = 3.0   # seconds before a read times out

        # Verify the connection with a real read if we have any tags configured
        enabled = [t for t in self.tags if t.get("enabled", True)]
        if enabled:
            result = client.Read(enabled[0]["address"])
            # "failure" in the status means a network problem, not just a missing tag
            if "failure" in str(result.Status).lower():
                raise ConnectionError(result.Status)

        self._client = client

    def _connect_s7(self) -> None:
        """
        Connect to a Siemens S7 PLC using python-snap7.

        snap7's connect() raises an exception automatically if the PLC
        cannot be reached, so no additional verification is needed here.
        """
        from snap7 import Client as S7Client

        client = S7Client()
        client.connect(self.ip, self.rack, self.slot)
        self._client = client

    # ── retry loop ────────────────────────────────────────────────────────

    def _start_retry(self) -> None:
        """Start the background retry thread if it is not already running."""
        if self._retry_thread and self._retry_thread.is_alive():
            return
        self._retry_thread = threading.Thread(
            target=self._retry_loop, daemon=True, name=f"retry-{self.name}"
        )
        self._retry_thread.start()

    def _retry_loop(self) -> None:
        """
        Background loop that retries the connection every 5 seconds.

        The loop exits when either:
          - _stop_event is set (disconnect() was called), or
          - the connection succeeds (_connected becomes True)

        Status is set to RETRYING between attempts so the GUI can show
        an appropriate indicator to the user.
        """
        retry_delay_s = 5   # seconds between reconnect attempts

        while not self._stop_event.is_set() and not self._connected:
            self._set_status(STATUS_RETRYING, f"Retrying in {retry_delay_s}s…")

            # Sleep in small increments so _stop_event is checked frequently
            # and the app doesn't hang for 5 seconds when closing
            for _ in range(retry_delay_s * 4):
                if self._stop_event.is_set():
                    return
                time.sleep(0.25)

            # Only try again if we haven't been told to stop
            if not self._stop_event.is_set():
                self._try_connect()

    # ── tag reading ───────────────────────────────────────────────────────

    def read_tags(self) -> dict:
        """
        Read all enabled tags from the PLC and return a dict:
            { "TagAddress": value_or_None, ... }

        If the read fails due to a communication error the connection is
        marked as ERROR and the retry loop is started automatically.
        Returns an empty dict on error.
        """
        if not self._connected or not self._client:
            return {}
        try:
            if self.plc_type == "ab":
                return self._read_ab()
            else:
                return self._read_s7()
        except Exception as e:
            # Communication dropped mid-read — trigger auto-retry
            self._connected = False
            self._set_status(STATUS_ERROR, str(e))
            self._start_retry()
            return {}

    def _read_ab(self) -> dict:
        """
        Read all enabled tags from an Allen-Bradley PLC in one batch call.

        pylogix's Read() accepts a list of tag names and returns a list of
        Response objects in the same order, which is much more efficient
        than calling Read() once per tag.
        """
        enabled   = [t for t in self.tags if t.get("enabled", True)]
        addresses = [t["address"] for t in enabled]
        if not addresses:
            return {}

        readings = self._client.Read(addresses)

        # Read() returns a single Response when given one tag, a list for many
        if not isinstance(readings, list):
            readings = [readings]

        return {
            tag["address"]: (reading.Value if reading.Status == "Success" else None)
            for tag, reading in zip(enabled, readings)
        }

    def _read_s7(self) -> dict:
        """
        Read all enabled tags from a Siemens S7 PLC one at a time.

        snap7 reads raw bytes from a Data Block (DB) at a given byte offset.
        The bytes are then unpacked into the correct Python type using the
        struct module.  Data type sizes:
            BOOL  1 byte   INT   2 bytes   DINT  4 bytes
            REAL  4 bytes  WORD  2 bytes   DWORD 4 bytes
        """
        import struct

        # Maps data type name → byte size for the db_read() call
        size_map = {
            "BOOL": 1, "INT": 2, "DINT": 4,
            "REAL": 4, "WORD": 2, "DWORD": 4,
        }

        results = {}
        for tag in self.tags:
            if not tag.get("enabled", True):
                continue

            addr   = tag["address"]
            dtype  = tag.get("data_type", "REAL")
            db_num = int(tag.get("db_number", 1))
            offset = int(tag.get("offset", 0))

            try:
                size = size_map.get(dtype, 4)
                raw  = self._client.db_read(db_num, offset, size)

                # Unpack the raw bytes according to the data type.
                # All Siemens values are big-endian (">").
                if dtype == "BOOL":
                    val = bool(raw[0])
                elif dtype == "INT":
                    val = struct.unpack(">h", raw)[0]      # signed 16-bit
                elif dtype == "DINT":
                    val = struct.unpack(">i", raw)[0]      # signed 32-bit
                elif dtype == "REAL":
                    val = round(struct.unpack(">f", raw)[0], 4)   # 32-bit float
                else:
                    # WORD / DWORD — treat as unsigned integer
                    val = int.from_bytes(raw, "big")

                results[addr] = val

            except Exception:
                # If one tag fails, store None and continue reading the rest
                results[addr] = None

        return results

    # ── trigger detection ──────────────────────────────────────────────────

    def check_trigger(self) -> bool:
        """
        Check whether the trigger tag has had a rising edge (False → True).

        The logger calls this at ~50 ms intervals when log_mode == "trigger".
        Returns True only on the transition from False to True (rising edge),
        so a tag that stays True does NOT produce repeated log rows.

        Returns False if:
          - No trigger tag is configured
          - The PLC is not connected
          - The tag read fails for any reason
        """
        if not self.trigger_tag or not self._connected:
            return False

        try:
            if self.plc_type == "ab":
                result = self._client.Read(self.trigger_tag)
                current_val = bool(result.Value) if result.Status == "Success" else False
            else:
                # For S7 trigger tags, read byte 0 of DB1 as a BOOL
                raw         = self._client.db_read(1, 0, 1)
                current_val = bool(raw[0])

            # Rising edge: was False last poll, now True
            rising_edge        = current_val and not self._prev_trigger
            self._prev_trigger = current_val
            return rising_edge

        except Exception:
            return False

    # ── diagnostics ───────────────────────────────────────────────────────

    def get_diagnostics(self) -> dict:
        """
        Return a dict of diagnostic information about this connection.

        Always safe to call — all errors are caught and reported in the
        returned dict rather than raised.  The Diagnostics screen calls
        this for every connection when the page is opened or refreshed.
        """
        # Base info that is always available, even when disconnected
        diag = {
            "ip":        self.ip,
            "plc_type":  self.plc_type,
            "status":    self.status,
            "error":     self.error_msg,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        }

        # Additional device info requires an active connection
        if self._connected and self._client:
            if self.plc_type == "ab":
                diag.update(self._diag_ab())
            else:
                diag.update(self._diag_s7())

        return diag

    def _diag_ab(self) -> dict:
        """
        Fetch Allen-Bradley device properties using pylogix.

        GetDeviceProperties() returns: ProductName, Revision, Vendor,
        SerialNumber, DeviceType.

        GetPLCTime() returns the current PLC clock time.

        GetTagList() returns all tags in the controller — we just count them.
        """
        d = {}

        # Device identity (model name, firmware version, serial number)
        try:
            r = self._client.GetDeviceProperties()
            if r.Status == "Success" and r.Value:
                dev = r.Value
                d["product_name"] = getattr(dev, "ProductName", "—")
                d["revision"]     = str(getattr(dev, "Revision",     "—"))
                d["vendor"]       = str(getattr(dev, "Vendor",       "—"))
                d["serial"]       = str(getattr(dev, "SerialNumber", "—"))
                d["device_type"]  = str(getattr(dev, "DeviceType",   "—"))
        except Exception as e:
            d["device_error"] = str(e)

        # PLC real-time clock
        try:
            t = self._client.GetPLCTime()
            if t.Status == "Success":
                d["plc_time"] = str(t.Value)
        except Exception:
            pass

        # Total tag count in the controller
        try:
            tags = self._client.GetTagList()
            if tags.Status == "Success" and tags.Value:
                d["tag_count"] = len(tags.Value)
        except Exception:
            pass

        return d

    def _diag_s7(self) -> dict:
        """
        Fetch Siemens S7 diagnostics using python-snap7.

        Only safe, low-risk calls are made here automatically:
          get_cpu_state()   – running / stopped  (safe on all S7 models)
          get_pdu_length()  – negotiated PDU size (safe on all S7 models)

        The higher-risk get_cpu_info() call (which can crash some S7-300
        PLCs) is intentionally NOT called here.  It is only triggered when
        the user explicitly clicks the "Get full CPU info" button on the
        Diagnostics screen.
        """
        d = {}

        # CPU running state — safe to call on all S7 PLCs
        try:
            state       = self._client.get_cpu_state()
            d["cpu_state"] = str(state)
        except Exception as e:
            d["cpu_state"] = f"unavailable ({e})"

        # PDU (Protocol Data Unit) length negotiated at connection time
        try:
            d["pdu_length"] = str(self._client.get_pdu_length())
        except Exception:
            d["pdu_length"] = "—"

        return d

    def get_s7_cpu_info(self) -> dict:
        """
        Fetch detailed Siemens CPU information via get_cpu_info().

        ⚠ WARNING: This call has been reported to crash some S7-300 PLCs,
        causing all LEDs to flash and requiring a full power cycle.
        Only call this on S7-1200 or S7-1500 PLCs.

        This method is only invoked when the user explicitly clicks the
        "Get full CPU info (risk)" button on the Diagnostics screen.
        """
        if not self._connected or not self._client:
            return {"error": "Not connected"}

        try:
            info = self._client.get_cpu_info()
            return {
                "module_type": str(getattr(info, "ModuleTypeName", "—")),
                "serial":      str(getattr(info, "SerialNumber",   "—")),
                "as_name":     str(getattr(info, "ASName",         "—")),
                "copyright":   str(getattr(info, "Copyright",      "—")),
            }
        except Exception as e:
            return {"error": str(e)}


# ── ConnectionManager ─────────────────────────────────────────────────────

class ConnectionManager:
    """
    Holds all PLCConnection objects and provides convenience methods for
    operating on all connections at once.

    The App class creates one ConnectionManager and passes it to both the
    CSVLogger and the GUI screens so they all share the same connection state.
    """

    def __init__(self, on_status_change=None):
        """
        Parameters
        ----------
        on_status_change : callable, optional
            Forwarded to every PLCConnection so the GUI gets notified of
            status changes on all connections.
        """
        # Dict of { connection_id: PLCConnection }
        self.connections      = {}
        self.on_status_change = on_status_change

    def add_connection(self, conn_cfg: dict) -> "PLCConnection":
        """
        Create a new PLCConnection from a config dict and register it.

        If a connection with the same ID already exists it is disconnected
        and replaced.  This handles the case where the user edits and
        re-saves an existing connection.
        """
        cid = conn_cfg["id"]
        if cid in self.connections:
            self.connections[cid].disconnect()   # clean up the old one first

        conn = PLCConnection(conn_cfg, self.on_status_change)
        self.connections[cid] = conn
        return conn

    def remove_connection(self, cid: str) -> None:
        """Disconnect and permanently remove a connection by its ID."""
        if cid in self.connections:
            self.connections[cid].disconnect()
            del self.connections[cid]

    def connect_all(self) -> None:
        """
        Connect all registered connections simultaneously.

        Each connection runs its own background thread so they all start
        in parallel rather than sequentially, which avoids long waits when
        multiple PLCs are configured.
        """
        for conn in self.connections.values():
            threading.Thread(
                target=conn.connect,
                daemon=True,
                name=f"connect-{conn.name}",
            ).start()

    def disconnect_all(self) -> None:
        """Disconnect all connections (called on app close)."""
        for conn in self.connections.values():
            conn.disconnect()

    def get_connection(self, cid: str) -> "PLCConnection | None":
        """Look up a connection by ID.  Returns None if not found."""
        return self.connections.get(cid)

    def read_all(self) -> dict:
        """
        Read tags from every currently-connected PLC and return:
            { connection_id: { "TagAddress": value, ... }, ... }

        Connections that are not in STATUS_CONNECTED are skipped.
        """
        return {
            cid: conn.read_tags()
            for cid, conn in list(self.connections.items())
            if conn.status == STATUS_CONNECTED
        }
