# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project follows Semantic Versioning.

## [0.1.8] - 2026-07-12

### Changed
- **Rebranded from "Sonar Mixer" to "SoundDeck"** — repositioned as a general Windows tray mixer that integrates with SteelSeries Sonar when available (window titles, tray, About, startup registry value, installer, executable name). SteelSeries Sonar is now optional. Old `SonarMixer` startup registry entry is cleaned up automatically.
- **Cyberpunk theme is now the default** for new installs (existing configs keep their choice).

### Added
- **Per-app mixer without SteelSeries** — when Sonar isn't running, the flyout now shows the Windows Master strip plus a scrollable list of every running app's own volume slider and mute (driven directly through Windows Core Audio sessions via `pycaw`, no virtual audio driver required). Replaces the previous Master-only fallback.
- Settings toggles: **Close on click outside** (hide the flyout when clicking anywhere outside) and **Lock window position** (disable header dragging).
- `hidapi` and `comtypes` are now listed explicitly in `requirements.txt` (previously `hidapi` was a silent optional dependency, so the battery indicator did not work on clean installs).

### Fixed
- **Idle CPU usage** — audio peak metering now only runs while the flyout is visible. Previously the audio stack was polled ~12×/second even when the panel was hidden in the tray, causing constant ~3% CPU. Hidden state is now near-idle.

## [0.1.7] - 2026-05-23

### Added
- Battery level badge on the tray icon: a coloured mini battery shape (green ≥50 %, orange ≤50 %, red ≤20 %, blue when charging) appears in the bottom-right corner of the icon when a headset is detected.
- Tray tooltip shows device name and battery percentage on hover.
- Background battery polling every 120 seconds keeps the tray icon up to date even when the flyout is closed.
- Flyout now has a draggable header bar — click and drag the "Sonar Mixer" title row to reposition the window anywhere on screen.
- Flyout has its own × close button; Escape key still works too.
- Flyout content is scrollable — channel strips are wrapped in a scroll area (max 430 px) so the panel stays compact even with many channels.

### Changed
- Flyout no longer closes when clicking outside; it stays open until explicitly dismissed via × button, Escape, or tray icon click.
- Window type changed from `Tool` to `Window + WindowStaysOnTopHint` with `WS_EX_TOOLWINDOW` set via API, fixing the Qt auto-hide behaviour while keeping the panel off the taskbar.

## [0.1.6] - 2026-05-21

### Added
- Dynamic channel mode: when SteelSeries GG / Sonar is not running, the mixer falls back to a single **Master** channel backed by the Windows default audio endpoint (via `pycaw`).
- Automatic reconnect: polls every 5 seconds when Sonar is unavailable and switches back to the full 4-channel mixer as soon as Sonar comes back online.
- `WindowsVolume` controller for Windows master volume and mute when in fallback mode.

### Fixed
- `AudioRoutingClient` and `SonarApiSwitcher` now re-discover Sonar's dynamic port on request failure, so app routing and device selection recover correctly after Sonar restarts.
- App session listing no longer blocks channel display if the routing endpoint is temporarily unreachable.

### Changed
- `SonarClient.reset()` allows a clean reconnect after a connection failure without restarting the app.

## [0.1.5] - 2026-05-21

### Added
- Headset battery indicator in the SOURCE device selector.
  - Reads SteelSeries Arctis headsets directly via HID (`0xb0` status command).
  - Shows battery percentage next to the combo, color-coded: green ≥50 %, orange 25–49 %, red <25 %.
  - Displays `⚡` prefix and charges while USB charging is detected.
  - Battery is polled once each time the flyout window opens (background thread, ~120 ms).
  - Label is hidden when a non-headset device is selected.

## [0.1.4] - 2026-05-21

### Added
- Cyberpunk theme toggle accessible from the tray menu and Settings window.
  - HUD top (`● REC` blinking bar) and bottom (`UPLINK / LAT / CH` strip) overlays.
  - Chamfered-corner panel and per-strip borders with pink/cyan accent colours.
  - `QGraphicsDropShadowEffect` glow on value labels and channel titles.
  - Zero-padded volume values with hex sub-label (`0xHH`) per routable channel.
  - `[ CH.XX ]` channel-index tags above each strip title.
  - Rajdhani font bundled (`Regular`, `SemiBold`, `Bold`) and loaded at startup; used for cyber chip labels and HUD text.
- Live Windows Core Audio activity meters via `audio_levels.py`.
- Custom tray icon SVG (`tray-icon.svg`).

### Changed
- Compact and expanded strip heights now scale up in cyber mode to accommodate the extra CH label row.
- Master icon hidden in cyber mode (replaced by chamfered strip decoration).
- Chip width in cyber mode now measured at the delegate's actual render size (9 pt) to prevent text overflow.

## [0.1.3] - 2026-05-20

### Added
- Console-style horizontal mixer flyout with live Windows Core Audio activity meters.
- Per-app chip rename/color overrides with config persistence.
- Settings window and refreshed tray menu actions.
- Separate EQ-bars tray icon and hardware-knob app icon.

### Changed
- Source selectors and chip styling now use a more opaque, compact Console treatment.
- Build defaults and docs updated for version `0.1.3`.

### Removed
- Legacy full-window mixer UI code that was no longer used by the tray flyout app.
- Claude Design handoff/export artifacts and local generated caches from the repository workspace.

## [0.1.2] - 2026-03-05

### Fixed
- Clicking transparent flyout corner areas no longer closes the window.
- Outside-click detection now uses cursor-position guard alongside activation-change events.

### Changed
- Flyout mute button replaced with a custom-drawn speaker icon (filled body + sound waves / diagonal strike for muted).
- Device selection dropdown popup now uses acrylic blur with accent-coloured selection highlight.
- Icon-to-title spacing in flyout channel strips reduced for a tighter layout.
- Build script now uses `SonarMixer.spec` directly; spec file paths are now relative (`SPECPATH`).

## [0.1.1] - 2026-03-03

### Added
- Shared `SOURCE` selector in flyout for linked Sonar output mode (when game/chat/media share one stream).
- Tray menu toggle: `Show logs` to control visibility of the flyout status/log line.

### Changed
- Narrowed flyout `MASTER` strip width for better overall space usage.
- Improved shared source naming format for more readable device labels.

## [0.1.0] - 2026-02-28

### Added
- PySide6 system-tray flyout mixer UI.
- Channel strips for Master, Game, Chat, and Media.
- Per-channel volume, mute, and output device selection.
- Drag-and-drop app routing chips between routable channels.
- App alias mapping support for known process names.
- Tray menu toggle for "Start with Windows" with Windows Registry integration.
- Installer build pipeline:
  - `build-installer.ps1`
  - `installer.iss` (Inno Setup)
- Open-source project docs:
  - `README.md`
  - `CONTRIBUTING.md`
  - `LICENSE`

### Changed
- Switched tray integration to Qt (`QSystemTrayIcon`).
- Migrated to compact flyout-first interaction model.
- Updated tray icon handling to use bundled assets.

### Fixed
- Auto-discover Sonar local API URL from GG IPC metadata instead of relying on hardcoded `http://127.0.0.1:7011`.
- Restored compatibility when Sonar runs on dynamic local ports (for example `http://127.0.0.1:5079`).
- Tray icon click now refreshes channel data before toggling the flyout.
- Reduced chip minimum width/padding so short app names (for example `Opera`) render without excess empty space.
