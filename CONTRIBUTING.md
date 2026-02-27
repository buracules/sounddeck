# Contributing

## Development Setup

```powershell
cd D:\Projects\AudioSwitcher\sonar-control-panel
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run

```powershell
.\.venv\Scripts\python app.py
```

## Code Guidelines

- Keep UI and business logic separated.
- Prefer targeted, minimal changes over broad rewrites.
- Preserve channel behavior correctness before visual polish.
- Avoid adding platform-specific hacks without a fallback.

## Commit Style

Use Conventional Commits, for example:

- `feat(ui): refine flyout channel strip spacing`
- `fix(routing): keep app list stable after route move`
- `docs(readme): update install and usage`

## Pull Requests

- Include short problem statement + solution summary.
- Attach screenshots for UI changes.
- Mention tested scenarios (tray open/close, drag/drop, device select, mute, refresh).
