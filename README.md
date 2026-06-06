# Cycling

Indoor cycling training app with BLE trainer support for Windows.

## Setup

```powershell
# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install
pip install -e .
```

## Quick start: full session workflow

```powershell
# 1. Set your FTP (Functional Threshold Power)
cycling ftp 250

# 2. Scan for nearby BLE devices (caches discovered devices)
cycling scan

# 3. List known devices (online/offline from last scan)
cycling devices

# 4. Record a training session — use name or address
cycling record JFICcycle

# 5. View session history
cycling history

# 6. View detailed report for session #1
cycling session 1
```

## Commands

| Command | Description |
|---------|-------------|
| `cycling scan` | Discover nearby BLE devices (caches results) |
| `cycling devices` | List known devices with online/offline status |
| `cycling live <address \| name>` | Connect and display live data (no recording) |
| `cycling record <address \| name>` | Connect and record a session to the database |
| `cycling history` | List past training sessions |
| `cycling session <id>` | View detailed report for a session |
| `cycling ftp [value]` | Get or set your FTP |
| `cycling zones` | Display training zones |
| `cycling version` | Show version |

## Options

- `cycling scan --timeout 5` — scan for 5 seconds
- `cycling scan --all` — show all BLE devices, not just cycling
- `cycling record <addr> --hr <hr_addr>` — also connect to a heart rate monitor

## Name resolution

After running `cycling scan`, devices are cached. You can refer to them by name:

```powershell
cycling live JFICcycle
cycling record JFICcycle --hr "HR Monitor"
cycling live AA:BB:CC:DD:EE:FF   # or still use raw address
```

Previously seen devices that are not found in the latest scan are shown as **Offline** in `cycling devices`.

## Web Dashboard

A web-based live dashboard is available with the same functionality as the CLI:

```bash
# Install web dependencies
pip install -e ".[web]"

# Start the web server
cycling-web

# Or using uvicorn directly
uvicorn cycling.web.server:app --host 0.0.0.0 --port 8080
```

Open http://localhost:8080 in your browser.

### Web Pages

| Route | Description |
|-------|-------------|
| `/` | Home — FTP status and recent sessions |
| `/live` | Live BLE data dashboard (connect, view power/HR/cadence/zones, record) |
| `/scan` | Scan for nearby BLE devices |
| `/history` | Past session history |
| `/session/{id}` | Detailed session report |
| `/zones` | Training zone definitions based on FTP |
| `/ftp` | Get or set FTP |

The live dashboard streams real-time data via Server-Sent Events (SSE) after connecting to a trainer. Start/stop recording to save sessions to the database.

## Example with HR monitor

```powershell
cycling record 6C:79:B8:A2:20:40 --hr D0:E5:3A:12:34:56
```

## Development

```powershell
pip install -e ".[dev]"
pytest
```
