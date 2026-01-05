# AtomX Release Checklist

## Versioning
- [ ] Set the release version (e.g., `0.9.0`) in README/docs and About dialog if present.
- [ ] Tag the release in git.

## Dependencies
- [ ] Regenerate `requirements.txt` from the current venv:  
  `python -m pip freeze > requirements.txt`
- [ ] Ensure PyQt6, cantools, python-can, qdarktheme, pytest, etc., are included.
- [ ] For PCAN users, include driver install steps in README.

## Assets & Data
- [ ] Include `ui/app logo.png` (used for app icon/splash).
- [ ] Include DBC files under `DBC/`.
- [ ] Include `CAN Configuration` (e.g., `can_messages.py`) and test sequences/templates.
- [ ] Keep `dist/` and build artifacts out of git (`.gitignore` already covers `dist/`).

## Build (example)
- PyInstaller (from the repo root, venv activated):  
  `pyinstaller --name AtomX --noconsole --add-data "DBC;DBC" --add-data "CAN Configuration;CAN Configuration" --add-data "Test Sequence;Test Sequence" main.py`
- Verify the bundled app shows the correct icon and starts without missing-module errors.
- Ensure no >100MB binaries are committed; distribute the installer/zip separately.

## Smoke Tests
- [ ] Launch app; verify splash/icon.
- [ ] Connect CAN (sim/hw). Start/stop cyclic CAN; check timing stability.
- [ ] Error & Warning tab periodic send (driver-level periodic); verify cycle times.
- [ ] Run Auto CAN Matrix Test Suite; confirm JSON/HTML reports saved under `Test Results/` with assertion bars and “Automated CAN Matrix Test Suite” name.
- [ ] Run a sample user sequence (e.g., Line and Load Regulation); confirm automatic HTML report (with duration/status) and trace/CSV logging are valid.
- [ ] Test “CAN / Set Signal Value” keeps other signals intact and continues TX.
- [ ] Trace/CSV files have valid timestamps (no garbage values).

## Docs & Onboarding
- [ ] Provide quick-start for the team:
  - Create venv: `python -m venv .venv && .venv\Scripts\activate`
  - Install deps: `python -m pip install -r requirements.txt`
  - Run: `python main.py`
  - Outputs: `Test Results/`, `logs/app.log`
  - Hardware notes: PCAN driver install; profile selection (`hw` default, `sim` for demo).
- [ ] Note the included logo, supported profiles, and any environment variables if needed.

## Release Notes
- [ ] Summarize key changes: driver-level periodic send; stable timing metrics; choice-to-code mapping for CAN Matrix assertions; report styling (assertion bars, suite rename); logo integration; DBC/timeouts fixes.
- [ ] Attach paths to example reports (CAN Matrix HTML/JSON) for reference.

