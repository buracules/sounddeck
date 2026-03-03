# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project follows Semantic Versioning.

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
