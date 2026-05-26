# Project Eris v4.3.1

PLC datalogger supporting Allen-Bradley (pylogix) and Siemens S7 (python-snap7).
Features interval and trigger-based logging, per-connection CSV files,
live dashboard with trend chart, diagnostics, help guide, and dark/light mode.

---

## Screen Shots

**1. Dashboard**

<img width="1022" height="692" alt="ProjectEris - 001 Dashboard" src="https://github.com/user-attachments/assets/5614f0d9-deb9-480a-b52d-4cb1e313d9e2" />

**2. Data Viewer**

<img width="1022" height="692" alt="ProjectEris - 002 Data Viewer" src="https://github.com/user-attachments/assets/119b234e-3e78-436c-ba39-16ad322744be" />

**3. Connections**

<img width="1022" height="692" alt="ProjectEris - 003 Connections" src="https://github.com/user-attachments/assets/5344f132-b12d-40cc-96fa-bfcac8f07e71" />

**4. CSV Logs**

<img width="1022" height="692" alt="ProjectEris - 004 CSV Logs" src="https://github.com/user-attachments/assets/631e8793-0e76-4543-8ce0-b7f68432a679" />

**5. Diagnostics**

<img width="1022" height="692" alt="ProjectEris - 005 Diagnostics" src="https://github.com/user-attachments/assets/24ee9989-c81f-45a6-946d-c45a56850c7e" />

**6. Help**

<img width="1022" height="692" alt="ProjectEris - 006 Help" src="https://github.com/user-attachments/assets/80cbb159-0624-4e70-a2dd-15053ad15ff2" />

**7. Settings**

<img width="1022" height="692" alt="ProjectEris - 007 Settings" src="https://github.com/user-attachments/assets/1c0e1a5b-0ca5-4eba-9b5e-a5abd4a65313" />

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
