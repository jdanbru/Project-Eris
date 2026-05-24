"""
config.py
─────────
Project Eris – persistent configuration manager.

All user settings (connections, logging preferences, theme, etc.) are
stored as a JSON file on disk so they survive between sessions.

File location:  C:\\Users\\<YourName>\\ProjectEris\\config.json

Typical usage:
    from config import load_config, save_config
    cfg = load_config()          # returns a dict
    cfg["log_interval"] = 2.0
    save_config(cfg)             # writes back to disk
"""

import json
from pathlib import Path


# ── default values ────────────────────────────────────────────────────────
# These are used the very first time the app runs (no config file yet),
# and also as a fallback if a key is missing from an older config file.

DEFAULT_CONFIG = {
    "connections":      [],          # list of connection dicts (see connections.py)
    "log_interval":     1.0,         # default poll interval in seconds
    "csv_folder":       str(Path.home() / "ProjectEris" / "Logs"),
    "timestamp_format": "iso",       # "iso" or "excel"
    "auto_connect":     True,        # connect to all PLCs on startup
    "auto_log":         False,       # start logging automatically on startup
    "minimize_to_tray": False,       # minimize to system tray instead of closing
    "theme":            "light",     # "light" or "dark"
}


# ── path helpers ──────────────────────────────────────────────────────────

def get_config_path() -> Path:
    """
    Return the full path to config.json, creating the parent directory
    if it does not yet exist.
    """
    app_dir = Path.home() / "ProjectEris"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir / "config.json"


# ── load / save ───────────────────────────────────────────────────────────

def load_config() -> dict:
    """
    Load settings from disk and return them as a dict.

    If the file doesn't exist or is corrupted, the DEFAULT_CONFIG dict
    is returned instead so the app always has a valid configuration.
    Any keys present in DEFAULT_CONFIG but missing from the file (e.g.
    after an upgrade) are filled in with their default values.
    """
    path = get_config_path()
    if path.exists():
        try:
            with open(path, "r") as f:
                data = json.load(f)
            # Start from defaults so new keys are always present
            cfg = DEFAULT_CONFIG.copy()
            cfg.update(data)
            return cfg
        except Exception as e:
            print(f"[Config] Could not load config.json: {e}  — using defaults.")
    return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    """
    Write the current config dict to disk as formatted JSON.
    Silently logs any write errors rather than crashing the app.
    """
    path = get_config_path()
    try:
        with open(path, "w") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"[Config] Failed to save config.json: {e}")


# ── directory helpers ─────────────────────────────────────────────────────

def get_logs_dir(config: dict, conn_name: str = None) -> Path:
    """
    Return the directory where CSV log files should be written.

    If conn_name is provided (and the connection has 'separate_csv' enabled),
    a per-connection subdirectory is returned:
        <csv_folder>/<SafeConnectionName>/

    Otherwise the base csv_folder is returned.

    The directory is created automatically if it doesn't exist.
    """
    base = Path(config.get("csv_folder", DEFAULT_CONFIG["csv_folder"]))
    if conn_name:
        folder = base / _safe_name(conn_name)
    else:
        folder = base
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _safe_name(name: str) -> str:
    """
    Convert a connection name into a string that is safe to use as a
    folder name on Windows by replacing illegal characters with underscores.
    """
    return "".join(
        c if c.isalnum() or c in " _-" else "_"
        for c in name
    ).strip()
