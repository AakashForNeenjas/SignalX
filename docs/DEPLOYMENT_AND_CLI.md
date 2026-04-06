# Deployment & CLI Guide

This guide covers packaging AtomX and running sequences headlessly via CLI.

## CLI Runner (Headless)

Use `run_sequence.py` to execute a test sequence without the GUI.

### Examples
```bash
# Run in simulation profile (default DBC=RE)
python run_sequence.py --sequence "Test Sequence/sequence.json" --profile sim

# Specify a different DBC and log level
python run_sequence.py --sequence "Test Sequence/sequence.json" --dbc RE --log-level DEBUG

# Initialize instruments before running (for hardware)
python run_sequence.py --sequence "Test Sequence/sequence.json" --profile hw --init-instruments
```

### Behavior
- Loads profiles from `config_profiles/profiles.json` if present, else built-in defaults.
- Respects profile CAN interface/channel/bitrate and simulation flag.
- Loads DBC (default `RE.dbc`).
- Executes steps sequentially using the same Sequencer logic as the GUI; stops on first failure.
- Logs to `logs/app.log` (rotating JSON) and prints step messages to stdout.

### Sequence Format
- Supports current format `{ "meta": {...}, "steps": [...] }` and legacy list-only sequences.

## Packaging (PyInstaller)

Canonical build path (recommended, from repo root):
```powershell
.\build_atomx.ps1
```
- This is the default end-user release build (`--noconsole`).

Debug build with terminal output:
```powershell
.\build_atomx.ps1 -Console
```
- This uses `--console` for troubleshooting.
- Build branding source-of-truth is `ui/app logo.png`; the script auto-generates `ui/app_logo.ico` before packaging.

Fallback direct PyInstaller command:
Basic build command (from repo root):
```bash
pyinstaller --name AtomX --noconsole --icon "ui/app_logo.ico" --add-data "DBC;DBC" --add-data "CAN Configuration;CAN Configuration" --add-data "Test Sequence;Test Sequence" main.py
```

Notes:
- `--add-data` includes runtime assets (DBC, config, sample sequences). Adjust paths for your OS (use `:` on macOS/Linux).
- Ensure Qt plugins are found; PyInstaller usually bundles them automatically for PyQt6.
- If icon looks stale on a previously pinned taskbar shortcut, unpin and re-pin once after upgrade (Windows icon cache behavior).
- Output will be under `dist/AtomX/`.

## Tips & Troubleshooting
- Simulation-first: use `--profile sim` when no hardware is connected.
- Profiles: override addresses/bitrate per environment via `config_profiles/profiles.json`.
- Logs: check `logs/app.log` for detailed JSON logs from both CLI and GUI runs.
- Tests: run `python -m unittest discover tests` before packaging to catch regressions.
