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

Basic build command (from repo root):
```bash
pyinstaller --name AtomX --noconsole --add-data "DBC;DBC" --add-data "CAN Configuration;CAN Configuration" --add-data "Test Sequence;Test Sequence" main.py
```

Notes:
- `--add-data` includes runtime assets (DBC, config, sample sequences). Adjust paths for your OS (use `:` on macOS/Linux).
- Ensure Qt plugins are found; PyInstaller usually bundles them automatically for PyQt6.
- If you prefer a console build (for debugging), drop `--noconsole`.
- Output will be under `dist/AtomX/`.

## Tips & Troubleshooting
- Simulation-first: use `--profile sim` when no hardware is connected.
- Profiles: override addresses/bitrate per environment via `config_profiles/profiles.json`.
- Logs: check `logs/app.log` for detailed JSON logs from both CLI and GUI runs.
- Tests: run `python -m unittest discover tests` before packaging to catch regressions.
