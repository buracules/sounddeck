# SoundDeck

Modern PySide6 system-tray flyout mixer for Windows, with optional SteelSeries Sonar integration.

![SoundDeck Screenshot](docs/screenshot.png)
![Cyberpunk Theme](docs/cyber.png)

## Highlights

- Tray-first UX (`QSystemTrayIcon`) with flyout mixer panel
- Frameless dark gaming-style UI — **Cyberpunk theme on by default**
- Channels: `MASTER`, `GAME`, `CHAT`, `MEDIA`
- Per-channel volume and mute
- Per-channel output selection (routable channels)
- App routing chips with drag/drop between channels
- Local app alias support (e.g. `Gw2-64` -> `Guild Wars 2`)
- Works without SteelSeries: when Sonar isn't running, shows the Windows Master strip plus a per-app volume/mute mixer for every running app (via `pycaw` Core Audio sessions — no virtual audio driver needed)
- Headset battery badge on the tray icon (SteelSeries Arctis via HID)
- Settings window: theme, "close on click outside", "lock window position", compact view, startup, status line

## Requirements

- Windows 10/11
- Python 3.11+
- SteelSeries GG / Sonar (optional — enables the full 4-channel mixer and per-app routing)

## Installation

```powershell
cd sonar-control-panel
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run

```powershell
cd sonar-control-panel
.\.venv\Scripts\python app.py
```

## Build Installer (Windows)

1. Install Inno Setup 6 (`ISCC.exe` must be available under Program Files).
2. Build app + setup:

```powershell
cd sonar-control-panel
.\build-installer.ps1 -Version 0.1.7
```

Optional clean build:

```powershell
.\build-installer.ps1 -Version 0.1.7 -Clean
```

Outputs:

- App folder: `dist\SoundDeck\`
- Portable: `dist\SoundDeck-Portable-<version>.zip`
- Installer: `dist\SoundDeck-Setup-<version>.exe`

## CLI Utilities

```powershell
# Capture Sonar/GG IPC probe snapshot
.\.venv\Scripts\python app.py --capture-ipc .\ipc-capture.json

# Replay a captured payload against /v2/subAppActions
.\.venv\Scripts\python app.py --replay-ipc .\payload.json
```

## Project Structure

```text
app.py
requirements.txt
sounddeck/
  application.py       # app orchestration
  ui.py                # flyout UI and widgets
  tray.py              # Qt tray integration
  sonar_client.py      # sonar volume/mute wrapper
  sonar_api_switcher.py# output device selection
  audio_routing.py     # process routing
  windows_volume.py    # Windows master fallback volume (no Sonar)
  windows_apps.py      # per-app volume/mute mixer (no Sonar)
  assets/              # svg/png icons
```

## Open Source Notes

- License: MIT (see `LICENSE`)
- Contributions: see `CONTRIBUTING.md`
- Keep platform-specific behavior documented in PRs (Windows tray/flyout behavior)
