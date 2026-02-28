# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project follows Semantic Versioning.

## [1.0.0] - 2026-02-28

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
