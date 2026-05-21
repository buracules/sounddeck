# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project follows Semantic Versioning.

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
