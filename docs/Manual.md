# AtomX Manual (Code-Verified, Consolidated)

This manual is derived directly from the current codebase. It replaces prior docs. All statements reflect implemented behavior only.

---

## 1. Executive Overview
- AtomX is a PyQt6 desktop application for CAN and SCPI-based test automation.
- Supports simulation and hardware profiles (from `config_loader.py`).
- Drives CAN (via `CANManager`) and SCPI instruments (via `InstrumentManager` drivers).
- Runs scripted sequences through `Sequencer` (prefix-based action dispatch).
- Provides GUI (tabs for configuration, instruments, data gauges, tools) and a headless CLI (`run_sequence.py`).

## 2. Architecture
- UI (PyQt6): `MainWindow` (tabs), `Dashboard` (controls/sequence editor), `DataDashboard` (gauges), `InstrumentView` (web panes), icons/splash (`ui/resources.py`), styles (`ui/Styles.py`).
- Control: `Sequencer` runs steps on a worker thread; dispatches CAN/GS/PS/utility actions.
- CAN: `CANManager` handles connect/disconnect, DBC load, decode, signal cache, listeners, cyclic TX, CSV/TRC logging, CAN test methods.
- Instruments: `InstrumentManager` orchestrates SCPI drivers (PS/Grid/Scope), health checks, safe power-down.
- Config: `config_loader.py` profiles (sim/dev/hw defaults, optional `config_profiles/profiles.json` override); `config.py` fallbacks.
- Logging: JSON rotating app log + console (`logging_setup.py`); CAN trace logging in CSV/TRC (`CANManager`).
- CLI: `run_sequence.py` uses the same managers/Sequencer without GUI.

## 3. Folder Structure (Purpose)
- `main.py`: app bootstrap, theme/icon/splash, fade/slide animation, launches `MainWindow`.
- `logging_setup.py`: rotating JSON logging + console.
- `config_loader.py`: profile loader (sim/dev/hw).
- `run_sequence.py`: headless sequence runner (CLI).
- `core/`
  - `InstrumentManager.py`: SCPI drivers (ITECH PS/Grid, Siglent scope), init, health_report, safe_power_down.
  - `CANManager.py`: CAN connect, DBC init, signal cache, cyclic, CSV/TRC logging, CAN test actions.
  - `Sequencer.py`: threaded sequence executor; CAN/GS/PS/utility dispatch.
  - `DBCParser.py`: DBC load/decode.
  - `SignalManager.py`: DBC signal → UI callback mapping.
  - `driver_base.py`: instrument interfaces + `HealthStatus`.
- `ui/`
  - `MainWindow.py`: tabs, wiring, preflight, E-Stop, health check.
  - `Dashboard.py`: controls, sequence editor, CAN dialogs, E-Stop button, save/load with metadata popup.
  - `DataDashboard.py`: gauges (static layout) from CAN cache, lazy-loaded.
  - `InstrumentView.py`: web views for instrument UIs.
  - `Styles.py`: shared styles (incl. E-Stop).
  - `resources.py`: generated AtomX icon/splash.
- `docs/DEPLOYMENT_AND_CLI.md`: CLI usage, PyInstaller guidance.
- `Test Sequence/`: saved sequences (JSON).
- `CAN Configuration/`: CAN configs (messages, mapping).
- `DBC/`: DBC files (e.g., RE.dbc).
- `logs/`: app logs.
- `tests/`: unit tests.

## 4. Startup & Lifecycle
- Logging initialized (`setup_logging`), theme applied, icon/splash created, splash shown, MainWindow fades/slides in.
- Profiles loaded; core managers initialized (`InstrumentManager`, `DBCParser`, `SignalManager`, `CANManager`, `Sequencer`).
- Tabs added; Data/Instrument tabs lazy-loaded.

## 5. Configuration & Profiles
- Profiles from `config_profiles/profiles.json` if present; else built-in sim/dev/hw (`config_loader.py`).
- Fields: `simulation_mode`, `can` (interface/channel/bitrate), `instruments` (addresses), `logging` (level/file/dir).
- `config.py` provides CAN/instrument defaults as fallback.

## 6. UI (Key Elements & Workflows)
- Tabs: Configuration (Dashboard), Instrument (web views), Data (gauges), Error/Warn (placeholder), Tools (log viewer + health check).
- Dashboard controls:
  - Initialize Instruments; Connect/Disconnect CAN; Start/Stop Cyclic CAN; Start/Stop Trace; Run Sequence (preflight enforced); E-Stop.
  - Sequence editor: add/edit/delete/reorder/duplicate; status column; save/load (metadata popup: Name/Author/Description/Tags; cancel still saves with defaults).
  - CAN dialogs for 7 test actions (parameter validation in dialogs).
- Tools tab: Refresh Logs; Check Instrument Health (reports ✓/✗ to Output log); log auto-refresh when active.
- Data tab: gauges (static `SIGNALS` list) updated from CAN cache via timer; lazy-loaded.
- Instrument tab: embedded web views for grid/PS/scope URLs.
- Branding/animation: AtomX icon/splash; main window fade + slide.

## 7. Sequence Engine (Sequencer)
- Steps: `{ "action": <string>, "params": <string or JSON> }`.
- Threaded run; stops on first failure; emits `action_info` and `step_completed`.
- Action dispatch (prefix-based):
  - CAN: connect/disconnect; start/stop cyclic; start/stop trace; send/check/listen; CAN test methods (read/tolerance/conditional/wait/range/compare/set+verify).
  - GS: set/get V/I/Freq; measures (V/I/Freq, power, THD); power on/off; ramps; reset; IDN; error handling.
  - PS: connect/disconnect; output on/off; measure VI; set V/I; ramps; battery charge/discharge; sweeps; read/clear errors.
  - Utility: Wait.
  - Initialize Instruments.

## 8. CAN Manager
- Connect/disconnect (profile defaults if not provided); simulation mode generates DBC-valid traffic.
- DBC load seeds `message_definitions` and `signal_cache` (with lock).
- Listeners with lock; decode updates cache; message history keeps last 100.
- Cyclic CAN: start/stop all from `can_messages.py`; by-name helper.
- Logging: CSV/TRC in `Test Results/trace_<timestamp>.csv|.trc`; relative times, DLC, data bytes.
- Diagnostics: `get_diagnostics`, `print_diagnostics`.
- Test methods: read_signal_value; check_signal_tolerance; conditional_jump_check; wait_for_signal_change; monitor_signal_range; compare_two_signals; set_signal_and_verify.

## 9. Instruments & Drivers
- Addresses injected from profiles; simulation mode supported.
- Drivers (implement interfaces in `driver_base.py`):
  - ITECH6006 (PowerSupplyDriver): set/get V/I; power on/off; ramps; sweeps; battery charge/discharge; health_check.
  - ITECH7900 (GridEmulatorDriver): set/get V/I/Freq; power on/off; THD/power measures; health_check.
  - SiglentSDX (OscilloscopeDriver): run/stop; waveform query; *IDN?; health_check.
- InstrumentManager:
  - `initialize_instruments()`: connect all; returns success flag + messages.
  - `health_report()`: aggregates HealthStatus.
  - `safe_power_down()`: powers off PS/Grid.
  - `close_instruments()`.

## 10. Safety & Preflight
- Preflight (before Run Sequence): CAN must be connected; all instrument HealthStatus.ok must be True; otherwise run is blocked with a warning (Output log + QMessageBox + logger).
- E-Stop: stops Sequencer, stops cyclic CAN, powers down PS/Grid (best effort), logs warning.
- Simulation mode to avoid hardware side effects.

## 11. Logging
- App log: JSON rotating + console (default `logs/app.log`).
- CAN traces: CSV/TRC in `Test Results/`; start/stop via UI or Sequencer actions.
- Sequence messages: Output log (UI) + app logger.
- CLI: stdout + app log.

## 12. File & Directory Conventions
- Sequences: `Test Sequence/*.json` (meta+steps) or legacy list.
- CAN traces: `Test Results/trace_<YYYYMMDD_HHMMSS>.csv|.trc`.
- Logs: `logs/app.log`.
- DBC: `DBC/RE.dbc`.
- CAN config: `CAN Configuration/` (e.g., `can_messages.py`, `signal_mapping.json`).
 - Build output (PyInstaller): `dist/AtomX/`.

## 13. CLI (Headless)
- `python run_sequence.py --sequence "Test Sequence/sequence.json" --profile sim`
- Options: `--dbc`, `--init-instruments`, `--log-level`.
- Uses same managers/Sequencer; stops on failure; no E-Stop in CLI.

## 14. SCPI Command Summary (per driver)
- ITECH6006: `VOLT`, `CURR`, `MEAS:VOLT?`, `MEAS:CURR?`, `OUTP ON/OFF`, `SYST:ERR?`, `SYST:ERR:CLEAR`; ramps/sweeps implemented in Python.
- ITECH7900: `VOLT`, `CURR`, `FREQ`; `MEAS:VOLT?`, `MEAS:CURR?`, `MEAS:FREQ?`; `OUTP ON/OFF`; power/THD: `MEAS:POW:REAL?`, `MEAS:POW:REAC?`, `MEAS:POW:APP?`, `MEAS:CURR:HARMonic:THD?`, `MEAS:VOLT:HARMonic:THD?`; `*RST`.
- SiglentSDX: `TRMD AUTO`, `STOP`, `C1:WF? DAT2`, `*IDN?`.

## 15. Action-to-Backend Mapping
- CAN / Connect → `CANManager.connect`
- CAN / Disconnect → `CANManager.disconnect`
- CAN / Start/Stop Cyclic CAN → `CANManager.start_all_cyclic_messages` / `stop_all_cyclic_messages`
- CAN / Start/Stop Trace → `CANManager.start_logging` / `stop_logging`
- CAN / Send Message → `CANManager.send_message` (Sequencer parses params)
- CAN test actions → corresponding CANManager methods (read/tolerance/conditional/wait/range/compare/set+verify)
- GS actions → `InstrumentManager.itech7900` methods
- PS actions → `InstrumentManager.itech6000` methods
- Initialize Instruments → `InstrumentManager.initialize_instruments`
- Wait → Sequencer delay loop

## 16. UI Validation Ranges (Dialogs)
- Read Signal: timeout 0.1–60 s; signal required.
- Check Tolerance: expected ±10000; tolerance 0–10000; timeout 0.1–60 s; signal required.
- Conditional Jump: expected ±10000; tolerance 0–10000 (default 0.1); jump step 1–9999; signal required.
- Wait for Change: initial ±10000; timeout 0.1–60 s; poll 0.01–5 s; signal required.
- Monitor Range: min/max ±10000; duration 0.1–300 s; poll 0.1–10 s; signal required.
- Compare Signals: tolerance 0–10000; timeout 0.1–60 s; both signals required.
- Set & Verify: message ID 0–0x7FF; target ±10000; tolerance 0–10000; verify timeout 0.1–60 s; signal required.
- Ramp dialogs: start/end ±10000; step 0.0001–10000; delay 0–3600; tolerance 0–1000; retries 0–100.

## 17. Threading Model
- Sequencer: worker thread; `running` flag checked for stop/E-Stop.
- CANManager: notifier callback; simulation thread for synthetic traffic.
- UI: main Qt thread; timers (DataDashboard), events for dialogs/buttons.

## 18. Error Handling Patterns
- Methods often return `(bool, message)`; Sequencer stops on first failure.
- Preflight blocks on failed CAN or instrument health.
- E-Stop swallows secondary errors; logs warning.
- CAN connect failures return False/message; disconnect best-effort.

## 19. Diagnostics
- `CANManager.get_diagnostics/print_diagnostics`: connection status, rx/tx counts, cache sizes, listeners, DBC load.
- Health: `InstrumentManager.health_report` (Tools tab hook).
- Message history: last 100 decoded entries in CANManager.

## 20. Deployment & Packaging
- PyInstaller example (PowerShell):
  ```
  pyinstaller --name AtomX --noconsole `
    --add-data "DBC;DBC" `
    --add-data "CAN Configuration;CAN Configuration" `
    --add-data "Test Sequence;Test Sequence" main.py
  ```
- Ensure PyInstaller on PATH or call full path to `pyinstaller.exe`.
- Include data folders (DBC, CAN Configuration, Test Sequence) in build.

## 21. Troubleshooting
- PyInstaller not found: use full path or add Scripts to PATH.
- Preflight fails: connect CAN; ensure instrument health OK (Tools → Check Instrument Health).
- CAN connect errors: check interface/channel/bitrate; ensure DBC load success.
- Sequence stops early: inspect Output log; Sequencer stops on first failure.
- Trace empty: ensure CAN connected before start trace.
- Use simulation profile when hardware is absent.

## 22. Extension Checklist
- New instrument: implement interface in `driver_base`, add SCPI methods + health_check, wire into InstrumentManager init/health.
- New CAN action: add CANManager method; wire in Sequencer; optionally add UI dialog.
- New UI control/tab: add to Dashboard/MainWindow; connect signals; lazy-load heavy tabs.
- New Sequencer behavior: extend `_execute_action`; maintain `(bool, message)` and stop-on-failure semantics.
- Logging: use injected logger; CSV/TRC only for CAN traces via CANManager.

## 23. Example Sequences
- CAN smoke (sim): connect, start cyclic, read signal, stop cyclic, disconnect.
- PS/GS setpoints + CAN check: init instruments, connect CAN, set GS/PS, CAN tolerance check, disconnect.

## 24. System Requirements
- Python deps: PyQt6, PyQt6-WebEngine, python-can, cantools, pyvisa, pyqtdarktheme (see `requirements.txt`).
- Assets: `DBC/RE.dbc`, `CAN Configuration/`, writable `Test Sequence/` and `Test Results/`.
- Hardware mode: reachable SCPI instruments per profile addresses; CAN interface/channel per profile.

## 25. Audit Checklist
- Profiles validated (sim/dev/hw).
- DBC load succeeds at startup.
- Instrument health passes (Tools).
- Preflight enforced before run.
- E-Stop tested (stops sequence, cyclic CAN, powers down).
- CAN trace start/stop verified.
- CLI run tested (sim).
- PyInstaller build tested (if distributing).

## 26. Known Behaviors/Limits
- Sequencer has no built-in retries; stops on first failure.
- Ramps/sweeps are synchronous; cancellation via stop/E-Stop.
- DataDashboard layout is static.
- Save metadata dialog: cancel still saves using defaults.
- CLI lacks E-Stop (stops on failure only).

## 27. Future Improvements (Anchors)
- Soft limits/confirmations for PS/Grid setpoints.
- CLI E-Stop or retry support.
- Rich oscilloscope SCPI coverage.
- Configurable gauges/thresholds with alerts.
- Sequencer branching/loop constructs beyond current actions.
- Structured step-level reporting/export.

## 28. Additional Quick Reference & Workflows
- GUI workflows (Connect/Trace; Run sequence with preflight; Health check; Save sequence) and CLI workflows (sim/hw/debug) are as described in preceding sections.
- Preflight: fails if CAN disconnected or any instrument health check fails.
- E-Stop: stops sequence, cyclic CAN, powers down PS/Grid; logs warning.
- Logging: app log (JSON), CAN trace (CSV/TRC), sequence messages to Output/log.

---
