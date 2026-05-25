# Project Eris v4.3.1

PLC datalogger supporting Allen-Bradley (pylogix) and Siemens S7 (python-snap7).
Features interval and trigger-based logging, per-connection CSV files,
live dashboard with trend chart, diagnostics, help guide, and dark/light mode.

---

## Quick start

1. Install Python 3.13: https://www.python.org/ftp/python/3.13.3/python-3.13.3-amd64.exe
2. Double-click **setup.bat** — installs all dependencies
3. Double-click **launch.bat** — starts the app

## Build portable .exe

1. Complete quick start above
2. Double-click **build.bat**
3. Copy `dist\ProjectEris\` to any Windows PC — no install or admin rights needed

---

## What's new in v2

- **Interval logging**: configurable per connection (min 100ms)
- **Trigger logging**: logs one row per rising edge of a BOOL tag
- **Separate CSV per connection**: each connection can write its own file
- **Diagnostics screen**: device info, CPU state, firmware revision per connection
- **Help screen**: step-by-step connection setup guide with troubleshooting tips
- **Dark / light mode**: toggle button in the sidebar header
- **Project Eris logo**: displayed in sidebar

---

## Connection types

| PLC family               | Library   | Protocols      |
|--------------------------|-----------|----------------|
| ControlLogix, CompactLogix, Micro8xx | pylogix | EtherNet/IP CIP |
| Siemens S7-300/400/1200/1500 | python-snap7 | S7 over TCP |

---

## CSV file format

- Shared log: `~/ProjectEris/Logs/eris_YYYY-MM-DD_HH-MM-SS.csv`
- Per-connection: `~/ProjectEris/Logs/<ConnectionName>/eris_<Name>_YYYY-MM-DD_HH-MM-SS.csv`
- Columns: `timestamp`, then one column per enabled tag
- New file created each time logging starts

---

## Settings are saved to

`C:\Users\<YourName>\ProjectEris\config.json`

---

## Dependencies

| Package        | Purpose                  |
|----------------|--------------------------|
| customtkinter  | GUI framework            |
| pillow         | Logo image loading       |
| pylogix        | Allen-Bradley comms      |
| python-snap7   | Siemens S7 comms         |
| matplotlib     | Trend chart              |
