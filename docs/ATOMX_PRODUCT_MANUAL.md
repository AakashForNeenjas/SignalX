# AtomX Product Manual (Code-Verified)

> This document is derived directly from the current AtomX codebase. It supersedes previous docs. All statements reflect implemented behavior in the repository.

## 1) Executive Overview
- AtomX is a PyQt6 desktop application for CAN-based and SCPI-based test automation.
- Users: test engineers, automation developers, integrators.
- Modes: simulation (no hardware) and hardware (real devices) selected via profiles.
- Core capabilities: connect to CAN, load DBC, run cyclic CAN, log CSV/TRC traces, execute test sequences that drive grid emulator, power supply, oscilloscope, and CAN actions.

## 2) Application Lifecycle
- Entry: `main.py`
  - Initializes logging (`logging_setup.setup_logging`).
  - Applies dark theme (`qdarktheme`).
  - Builds app icon/splash (`ui/resources.py`), shows splash, then fades/slides in `MainWindow`.
- Profiles loaded from `config_loader.py` (default sim/dev/hw or `config_profiles/profiles.json`).
- Managers created in `MainWindow.initialize_core_components`: `InstrumentManager`, `DBCParser`, `SignalManager`, `CANManager`, `Sequencer`.
- UI tabs built in `MainWindow`: Configuration (Dashboard), Instrument (web views), Data (gauges, lazy-loaded), Error/Warn (placeholder), Tools (log viewer + health check).

## 3) Folder Structure (Purpose)
- `main.py` – app bootstrap, theme, splash, main window creation.
- `logging_setup.py` – JSON rotating file logging + console handler.
- `config_loader.py` – profile loader with defaults (sim/dev/hw).
- `run_sequence.py` – headless CLI sequence runner.
- `core/`
  - `InstrumentManager.py` – SCPI drivers (power supply, grid emulator, oscilloscope), init, health, safe power down.
  - `CANManager.py` – CAN connect, DBC init, signal cache, cyclic TX, CSV/TRC logging, CAN test methods.
  - `Sequencer.py` – threaded sequence executor; dispatches CAN/GS/PS/utility actions.
  - `DBCParser.py` – load/decode DBC.
  - `SignalManager.py` – DBC signal mapping to UI callbacks.
  - `driver_base.py` – abstract driver interfaces + `HealthStatus`.
- `ui/`
  - `MainWindow.py` – main window, tab wiring, preflight checks, E-stop, health hook.
  - `Dashboard.py` – controls & sequence editor; CAN dialogs; save/load with metadata popup; E-stop button.
  - `DataDashboard.py` – CAN gauge view (lazy-loaded).
  - `InstrumentView.py` – embedded web panes for instrument UIs.
  - `Styles.py` – shared styles (incl. E-stop button).
  - `resources.py` – generated icon/splash (AtomX branding).
- `docs/DEPLOYMENT_AND_CLI.md` – CLI usage, PyInstaller notes.
- `Test Sequence/` – stored sequences (JSON).
- `CAN Configuration/` – CAN configs (messages, mapping).
- `DBC/` – DBC files (e.g., RE.dbc).
- `logs/` – app logs.
- `tests/` – unit tests.

## 4) Architecture
- UI: PyQt6 widgets/dialogs; tabs created in `MainWindow`.
- Control layer: `Sequencer` executes steps on a worker thread; stops on first failure.
- CAN layer: `CANManager` manages connection, DBC-based decode, signal cache, cyclic TX, CSV/TRC logging, simulation.
- Instrument layer: `InstrumentManager` orchestrates SCPI drivers (power supply, grid emulator, oscilloscope); health and safe power down.
- Config: profiles (interface/channel/bitrate, addresses, logging level, simulation flag).
- Logging: JSON rotating (app), CSV/TRC (CAN traces), stdout (CLI).
- CLI: `run_sequence.py` reuses Sequencer/managers without GUI.

## 5) UI & Workflows (Dashboard)
- Buttons: Initialize Instruments, Connect/Disconnect CAN, Start/Stop Cyclic CAN, Start/Stop Trace, Run Sequence, E-Stop.
- Sequence editor: add/edit/delete/reorder/duplicate steps; status column; save/load.
- Save sequence: “Test Details” popup (Name/Author/Description/Tags). Cancel still saves with defaults.
- CAN action dialogs (parameter capture) for:
  - Read Signal Value
  - Check Signal (Tolerance)
  - Conditional Jump
  - Wait For Signal Change
  - Monitor Signal Range
  - Compare Two Signals
  - Set Signal and Verify
- Tools tab: log viewer (auto-refresh when active), Refresh button, Check Instrument Health.
- Data tab: gauges (lazy load) fed by CAN signal cache.
- Instrument tab: embedded web views for grid/PS/scope URLs.

## 6) Sequence Engine (core/Sequencer.py)
- Steps: list of `{ "action": <str>, "params": <str|json> }`.
- Threaded run; halts on first failure; emits `action_info` and `step_completed` signals.
- Action dispatch:
  - `CAN / ...`: connect/disconnect; start/stop cyclic; start/stop trace; send/check/listen; CAN test actions delegated to `CANManager`.
  - `GS / ...`: set voltage/current/frequency; measures; power on/off; ramp up/down; THD/power measures.
  - `PS / ...`: connect/disconnect; output on/off; set V/I; ramp up/down; battery charge/discharge; sweeps.
  - Utility: Wait.
  - Initialize Instruments.

## 7) CAN Manager (core/CANManager.py)
- Connect/disconnect with defaults from profile; simulation mode synthesizes DBC-based traffic.
- DBC initialization caches message definitions; seeds signal cache (thread-safe).
- Listeners guarded by lock; message decode updates cache; CSV/TRC logging if enabled.
- Cyclic CAN: start/stop all based on `can_messages.py`.
- Logging: CSV/TRC in `Test Results/trace_<timestamp>.{csv,trc}` with relative timestamps and data bytes.
- Diagnostic methods: `get_diagnostics`, `print_diagnostics`.
- CAN test methods (used by Sequencer and UI dialogs): read value, check tolerance, conditional jump check, wait for change, monitor range, compare signals, set signal and verify (round-trip).

## 8) Instruments (core/InstrumentManager.py, drivers)
- Addresses injected from profile/config; simulation mode supported.
- Drivers implement abstract interfaces (`driver_base.py`):
  - `ITECH6006` (PowerSupplyDriver): set/get V/I, power on/off, ramps, sweeps, battery charge/discharge, health_check.
  - `ITECH7900` (GridEmulatorDriver): set/get V/I/Freq, power on/off, health_check.
  - `SiglentSDX` (OscilloscopeDriver): basic query, health_check via `*IDN?`.
- InstrumentManager:
  - `initialize_instruments()` connects all; returns success flag + messages.
  - `health_report()` returns `HealthStatus` per device.
  - `safe_power_down()` powers off PS/Grid.
  - `close_instruments()` disconnects all.

## 9) Safety & Preflight
- Preflight (before Run Sequence in `MainWindow.on_run_sequence`): requires CAN connected and all instrument health checks passing; otherwise warns and aborts run.
- E-Stop (`MainWindow.on_estop`):
  - Stops Sequencer.
  - Stops cyclic CAN.
  - Powers down instruments via `safe_power_down`.
  - Logs warning to Output and logger.
- Simulation mode available via profile to avoid hardware interaction.

## 10) Sequence Files
- Save format: `{ "meta": {name, author, description, tags, version, last_modified}, "steps": [...] }`.
- Load supports legacy list-only format.
- Metadata entered via “Test Details” popup on save (defaults used if canceled).

## 11) Logging
- App log: JSON rotating + console (`logging_setup.py`), default `logs/app.log`.
- CAN trace: CSV + TRC via `CANManager.start_logging` in `Test Results/`.
- Sequence run: messages to Output log (UI) and app logger.

## 12) CLI Runner (run_sequence.py)
- Headless execution of sequences without GUI.
- Args: `--sequence` (required), `--profile` (default sim), `--dbc` (default RE), `--init-instruments`, `--log-level`.
- Loads profiles/config, DBC, instantiates managers/Sequencer, runs steps sequentially, logs to stdout and app log.

## 13) Startup Branding & Animation
- Icon/splash generated (`ui/resources.py`) with “AtomX”.
- Splash shown; main window fades and slides in (`main.py`).

## 14) Deployment (from docs/DEPLOYMENT_AND_CLI.md)
- PyInstaller example (PowerShell):
```
pyinstaller --name AtomX --noconsole `
  --add-data "DBC;DBC" `
  --add-data "CAN Configuration;CAN Configuration" `
  --add-data "Test Sequence;Test Sequence" main.py
```
- Ensure PyInstaller is on PATH or call full path to `pyinstaller.exe`.

## 15) Testing
- Unit tests:
  - `tests/test_config_loader.py`: default profiles structure and fallback.
  - `tests/test_actions.py`: Sequencer dispatch for CAN/GS/PS using dummy drivers.

## 16) Developer Notes (from code conventions)
- Sequencer action routing expects `"PREFIX / Action Name"`; params often JSON or simple strings.
- CAN actions use `CANManager` methods that return tuples (bool + data/message).
- Health checks return `HealthStatus(ok: bool, message: str)`.
- Simulation mode toggled via profile flag `simulation_mode`.

## 17) Known UI Elements (wiring)
- Dashboard signals to MainWindow: init instrument, connect/disconnect CAN, start/stop cyclic, start trace, run sequence, stop sequence, E-stop.
- Tools tab: Refresh log, Check Instrument Health (calls `InstrumentManager.health_report`).
- Data tab: lazy load of `DataDashboard` gauges.

## 18) Error Handling Patterns
- Sequencer: stops on first failed action; logs message.
- Preflight: blocks run if CAN disconnected or any instrument health is not OK.
- E-Stop: best-effort shutdown; ignores secondary errors.
- CAN connect failures: returns `(False, message)` and logs.

## 19) Extension Points
- New actions: add to `Sequencer._execute_action` with prefix handling.
- New CAN methods: add to `CANManager`, then expose via Sequencer and optional UI dialog.
- New instruments: implement `GridEmulatorDriver` / `PowerSupplyDriver` / `OscilloscopeDriver`, wire into `InstrumentManager`.
- UI additions: extend Dashboard or add tabs in `MainWindow`.

---

This manual reflects the current repository state (files inspected: main.py, logging_setup.py, config_loader.py, run_sequence.py, core/*, ui/*, docs/DEPLOYMENT_AND_CLI.md, tests/*). For deeper SCPI or CAN signal details, consult the respective driver implementations and `CAN Configuration`/DBC files.***

---

## 20) SCPI Instrument Reference (Code-Verified)

### Power Supply (ITECH6006) – Implements `PowerSupplyDriver`
- **Connect/Disconnect**: via `InstrumentDriver.connect/ disconnect` (pyvisa). Simulation mode prints commands.
- **Set/Measure**:
  - Set voltage: `VOLT {voltage}`
  - Set current: `CURR {current}`
  - Measure voltage: `MEAS:VOLT?`
  - Measure current: `MEAS:CURR?`
- **Power Control**: `OUTP ON`, `OUTP OFF`
- **Ramps**:
  - `ramp_up_voltage(target, step, delay, tolerance, retries)`: looped sets with verify; re-issues on tolerance failure.
  - `ramp_down_voltage(target, step, delay, tolerance, retries)`: same, decreasing.
- **Sweeps**:
  - `sweep_voltage_and_log(start, step, end, delay, log_path=None)`: iterates set/measure pairs; optional CSV logging.
  - `sweep_current_and_log(start, step, end, delay, log_path=None)`: same for current.
- **Battery charge/discharge helpers**: set V/I then `OUTP ON`.
- **Errors**: `SYST:ERR?`, `SYST:ERR:CLEAR`
- **Health check**: reads V/I; reports `HealthStatus`.

### Grid Emulator (ITECH7900) – Implements `GridEmulatorDriver`
- **Connect/Disconnect**: `InstrumentDriver` base.
- **Set/Measure**:
  - Voltage: `VOLT {voltage}`, measure `MEAS:VOLT?`
  - Current: `CURR {current}`, measure `MEAS:CURR?`
  - Frequency: `FREQ {freq}`, measure `MEAS:FREQ?`
- **Power Control**: `OUTP ON`, `OUTP OFF`
- **Ramps**: simple set; optional `VOLT:RAMP:RATE {rate}`
- **THD/Power measurements** (Sequencer uses):
  - Real power: `MEAS:POW:REAL?`
  - Reactive: `MEAS:POW:REAC?`
  - Apparent: `MEAS:POW:APP?`
  - THD current: `MEAS:CURR:HARMonic:THD?`
  - THD voltage: `MEAS:VOLT:HARMonic:THD?`
- **Health check**: reads grid V/I.

### Oscilloscope (SiglentSDX) – Implements `OscilloscopeDriver`
- **Connect/Disconnect**: base.
- **Commands**:
  - Run: `TRMD AUTO`
  - Stop: `STOP`
  - Waveform: `C1:WF? DAT2`
  - Health: `*IDN?`
- Minimal integration; extend by adding SCPI in `SiglentSDX`.

### InstrumentManager orchestration
- Initializes drivers with profile addresses.
- `initialize_instruments()`: connect all; returns success flag + message log.
- `health_report()`: aggregates `HealthStatus` from drivers.
- `safe_power_down()`: powers off PS and Grid (best-effort).
- `close_instruments()`: disconnects all.

---

## 21) CAN Communication Reference (Code-Verified)

### Connection & DBC
- `CANManager.connect(interface=None, channel=None, bitrate=None)`: uses profile defaults or provided args.
- Simulation mode: generates DBC-valid traffic via `_simulate_traffic`.
- DBC load: `DBCParser.load_dbc_file("RE")` populates `message_definitions` and seeds `signal_cache`.

### Signal Cache & Listeners
- Thread-safe `signal_cache` with lock; updated on RX decode.
- Listeners list guarded by lock; `add_listener`, `remove_listener`.
- Message decode: quick lookup by arbitration_id; update cache with values and timestamps.

### Logging
- `start_logging(filename_base)`: creates `Test Results/<base>.csv` and `.trc`, writes headers, relative timestamps, DLC, data bytes.
- `stop_logging()`: closes files.
- TRC format: message counter, relative time, ID, Rx/Tx, DLC, data bytes.

### Cyclic Messages
- `start_all_cyclic_messages()` / `stop_all_cyclic_messages()`: uses `can_messages.py` definitions; encodes via DBC; starts/stops periodic TX.
- `start_cyclic_message_by_name(message_name, signals_dict, cycle_time_ms)`: encodes and transmits periodically.

### Diagnostics
- `get_diagnostics()`: connection status, counts, cache size, listeners, DBC load state, etc.
- `print_diagnostics()`: console dump.

### CAN Test Methods (Sequencer uses)
- `read_signal_value(signal_name, timeout)`
- `check_signal_tolerance(signal_name, expected_value, tolerance, timeout)`
- `conditional_jump_check(signal_name, expected_value, tolerance)`
- `wait_for_signal_change(signal_name, initial_value, timeout, poll_interval)`
- `monitor_signal_range(signal_name, min_val, max_val, duration, poll_interval)`
- `compare_two_signals(signal1, signal2, tolerance, timeout)`
- `set_signal_and_verify(message_id, signal_name, target_value, verify_timeout, tolerance)`
- Each returns tuples (bool + data/message) with timeouts and tolerance checks.

---

## 22) Sequence Engine Reference (Code-Verified)

### Step Format
- `{ "action": <string>, "params": <string or JSON> }`

### Execution Flow
- Threaded run in `Sequencer._run_sequence`; stops on first failure.
- Emits `action_info` (message) and `step_completed` (status) signals.
- `running` flag checked to allow external stop/E-stop.

### Action Dispatch (patterns in `Sequencer._execute_action`)
- Prefix-based:
  - `CAN / ...`:
    - Connect/Disconnect
    - Start/Stop Cyclic CAN
    - Start/Stop Trace
    - Send Message (JSON or comma-separated ID/data)
    - Start/Stop Cyclic By Name
    - Check/Listen for Message
    - CAN test actions (mapped to `CANManager` methods)
  - `GS / ...` (Grid Emulator):
    - Set voltage/current/frequency
    - Measure voltage/current/frequency
    - Measure power real/reactive/apparent
    - Measure THD current/voltage
    - Power ON/OFF
    - Ramp Up/Down Voltage (JSON: start/step/end/delay/tolerance/retries)
    - Reset System, Get IDN, Check Error, Clear Protection
  - `PS / ...` (Power Supply):
    - Connect/Disconnect
    - Output ON/OFF
    - Measure VI
    - Set Voltage/Current
    - Ramp Up/Down Voltage (JSON: start/step/end/delay/tolerance/retries)
    - Battery Set Charge/Discharge (JSON with voltage/current)
    - Read/Clear Errors
    - Sweep Voltage/Current (JSON: start/step/end/delay/log_file)
  - Utility: Wait.
  - Initialize Instruments.

### Preflight & Safety (MainWindow)
- Preflight before run: requires CAN connected and all instrument health checks passing; otherwise warns and aborts run.
- E-Stop: stops Sequencer, stops cyclic CAN, powers down instruments.

---

## 23) UI Reference (Code-Verified)

### Main Tabs (MainWindow)
- Configuration: Dashboard (controls + sequence editor)
- Instrument: web views (grid/PS/scope URLs)
- Data: lazy-loaded gauges (CAN signal cache)
- Error and Warnings: placeholder
- Tools: log viewer (auto-refresh on focus), Refresh Logs, Check Instrument Health

### Dashboard Controls & Signals
- Initialize Instruments → `MainWindow.on_init_instrument`
- Connect CAN / Disconnect CAN
- Start Cyclic CAN / Stop Cyclic CAN
- Start Trace (CSV/TRC) / Stop Trace
- Run Sequence (preflight enforced) / E-Stop
- Sequence editor (table): add/edit/delete/reorder/duplicate; status updates
- Save/Load Sequence: “Test Details” popup (Name/Author/Description/Tags; save proceeds even if canceled, using defaults)
- CAN dialogs: capture params for 7 CAN test actions

### Tools Tab
- Log viewer with Refresh
- Check Instrument Health → `InstrumentManager.health_report` (logs ✓/✗)

### Animations/Branding
- Splash with AtomX icon; main window fade + slide-in; app icon applied globally.

---

## 24) Logging Specification (Code-Verified)

- **App Log**: JSON rotating + console (default `logs/app.log`), configured in `logging_setup.py`.
- **CAN Trace**: CSV + TRC via `CANManager.start_logging`, stored in `Test Results/trace_<timestamp>.{csv,trc}`.
  - CSV columns: Time (ms), Type (Rx/Tx), ID (hex), DLC, Data bytes.
  - TRC: message counter, relative time, ID, Rx/Tx, DLC, data bytes.
- **Sequence Messages**: emitted to Output log (UI) and app logger via Sequencer/MainWindow.
- **CLI**: `run_sequence.py` logs to stdout and app log.

---

## 25) Configuration & Profiles (Code-Verified)

- `config_loader.py`: loads profiles from `config_profiles/profiles.json` if present; otherwise uses built-in `sim`, `dev`, `hw`.
- Profile fields: `simulation_mode`, `can` (interface/channel/bitrate), `instruments` (addresses), `logging` (level/file/dir).
- `config.py`: CAN defaults, cyclic messages template, instrument addresses (fallback).

---

## 26) Developer Extension Notes (Code-Verified Patterns)

### Add a new Sequencer action
- Extend `Sequencer._execute_action` for a new prefix or action name.
- Call into the appropriate manager/driver; return `(bool, message)`.

### Add a new CAN method
- Implement in `CANManager` with tuple return and timeout handling.
- Wire into Sequencer dispatch under `CAN / ...`.
- (Optional) Add a Dashboard dialog for parameters.

### Add a new instrument driver
- Implement `PowerSupplyDriver`, `GridEmulatorDriver`, or `OscilloscopeDriver` from `driver_base.py`.
- Mirror existing drivers (e.g., ITECH7900) with SCPI commands.
- Wire it into `InstrumentManager` initialization and `health_report`.

### Add UI elements
- Dashboard: add buttons/dialogs; connect signals to `MainWindow`.
- Tabs: modify `MainWindow` to add a new tab; lazy-load if heavy.

---

## 27) Troubleshooting (Code-Based)

- **PyInstaller not found**: use full path to `pyinstaller.exe` or add Scripts folder to PATH.
- **Preflight failure**: ensure CAN is connected (`CAN Connected`) and instrument health is OK (Tools → Check Instrument Health).
- **CAN connect errors**: verify profile interface/channel/bitrate; check DBC load message.
- **E-Stop**: use to halt a hung sequence; it stops Sequencer, cyclic CAN, and powers down PS/Grid.
- **Simulation mode**: use `--profile sim` (CLI) or sim profile in GUI to avoid hardware.

---

## 28) Deployment & CLI (Reminder)

- CLI run:
  ```bash
  python run_sequence.py --sequence "Test Sequence/sequence.json" --profile sim
  # hardware
  python run_sequence.py --sequence "Test Sequence/sequence.json" --profile hw --init-instruments
  ```
- PyInstaller (PowerShell):
  ```powershell
  pyinstaller --name AtomX --noconsole `
    --add-data "DBC;DBC" `
    --add-data "CAN Configuration;CAN Configuration" `
    --add-data "Test Sequence;Test Sequence" main.py
  ```
- Ensure PyInstaller is on PATH or call full path.

---

## 29) Safety Notes (As Implemented)

- Preflight blocks sequence start if CAN disconnected or instruments unhealthy.
- E-Stop provides immediate halt + power-down (best-effort).
- Simulation profile available to avoid hardware interaction.

---

## 30) Current Limitations (Observed)

- DataDashboard gauges use static layout (no configurable layout/thresholds after rollback).
- Oscilloscope driver is minimal (run/stop/waveform/IDN); extend for deeper use.
- Ramping/sweeps are synchronous loops (no async cancellation besides E-Stop).
- Sequence branching beyond provided actions is limited; add custom logic in Sequencer if needed.

---

## 31) API Reference (Core Classes & Key Methods – Code-Verified)

### logging_setup.py
- `setup_logging(log_dir="logs", filename="app.log", level="INFO", max_bytes=1_000_000, backup_count=3) -> (Logger, log_path)`

### config_loader.py
- `load_profiles(path="config_profiles/profiles.json") -> dict`
- `get_profile(name, profiles) -> dict`
- `DEFAULT_PROFILES`: sim/dev/hw with CAN/instrument/logging fields.

### run_sequence.py (CLI)
- `load_sequence_file(path) -> list`
- `run_sequence(steps, sequencer, logger)`
- CLI args: `--sequence`, `--profile`, `--dbc`, `--init-instruments`, `--log-level`.

### core.driver_base.py
- Interfaces: `PowerSupplyDriver`, `GridEmulatorDriver`, `OscilloscopeDriver`
- `HealthStatus(ok: bool, message: str)`

### core.DBCParser.py
- `load_dbc_file(filename=None) -> (bool, message)`
- `decode_message(msg_id, data) -> dict or None`
- `get_signal_info(signal_name) -> dict or None`
- `get_all_signals() -> dict`
- `list_messages() -> list`

### core.SignalManager.py
- `load_signal_mapping(filename="signal_mapping.json") -> (bool, message)`
- `register_ui_callback(ui_element_name, callback)`
- `process_can_message(msg_id, data)`
- `get_signal_value(signal_name, msg_id, data)`
- `list_mapped_signals()`

### core.CANManager.py (selected)
- `connect(interface=None, channel=None, bitrate=None) -> (bool, message)`
- `disconnect()`
- `start_logging(filename_base) -> path_base`
- `stop_logging()`
- `start_all_cyclic_messages() -> (started, failed)`
- `stop_all_cyclic_messages() -> bool`
- `add_listener(callback)`, `remove_listener(callback)`
- `get_diagnostics()`, `print_diagnostics()`
- CAN test methods: `read_signal_value`, `check_signal_tolerance`, `conditional_jump_check`, `wait_for_signal_change`, `monitor_signal_range`, `compare_two_signals`, `set_signal_and_verify`.
- Internal caches: `signal_cache`, `message_history`; guarded by locks.

### core.InstrumentManager.py
- `initialize_instruments() -> (bool, message_log)`
- `health_report() -> dict[str, HealthStatus]`
- `safe_power_down()`
- `close_instruments()`
- Drivers:
  - `ITECH6006`: set/get V/I, power on/off, ramps, sweeps, battery charge/discharge, health_check.
  - `ITECH7900`: set/get V/I/Freq, power on/off, THD/power measures, health_check.
  - `SiglentSDX`: run/stop/waveform, *IDN?, health_check.

### core.Sequencer.py
- Signals: `step_completed`, `action_info`, `sequence_finished`.
- `set_steps(steps)`
- `start_sequence()`, `stop_sequence()`
- `_execute_action(action, params, index)` dispatches CAN/GS/PS/utility actions.

### ui.resources.py
- `create_app_icon() -> QIcon`
- `create_splash_pixmap() -> QPixmap`

### ui.MainWindow.py (selected handlers)
- `initialize_core_components(profile_name)`
- `on_init_instrument`, `on_connect_can`, `on_disconnect_can`
- `on_start_cyclic`, `on_stop_cyclic`
- `on_start_trace`
- `on_run_sequence` (preflight enforced)
- `on_stop_sequence`
- `on_estop` (E-Stop: stop sequence, stop cyclic, power down)
- `on_check_health` (Tools tab)
- Lazy-load helpers: `ensure_data_tab_built`, `ensure_instrument_tab_built`

### ui.Dashboard.py (selected)
- Signals: `sig_init_instrument`, `sig_connect_can`, `sig_disconnect_can`, `sig_start_cyclic`, `sig_stop_cyclic`, `sig_start_trace`, `sig_run_sequence`, `sig_stop_sequence`, `sig_estop`.
- Sequence table management: add/edit/delete/reorder/duplicate; save/load; status updates.
- Save sequence prompts “Test Details” dialog; saves meta+steps JSON.
- CAN dialogs: read value, tolerance check, conditional jump, wait change, monitor range, compare signals, set & verify.

### ui.DataDashboard.py
- Gauges built from static `SIGNALS` list; updates via CAN signal cache; lazy-loaded.

### ui.InstrumentView.py
- Three web views for Grid, PS, Scope URLs; user-editable addresses in UI fields.

### ui.Styles.py
- Shared styles; special styling for E-Stop button.

---

## 32) Developer How-To (Code-Grounded)

### Build & Run (GUI)
```bash
python -m pip install -r requirements.txt
python main.py
```

### Run Headless (CLI)
```bash
python run_sequence.py --sequence "Test Sequence/sequence.json" --profile sim
```

### Add a New Instrument Driver
1. Implement the appropriate interface in `core/driver_base.py` (PowerSupplyDriver / GridEmulatorDriver / OscilloscopeDriver).
2. Create a class with SCPI methods mirroring `ITECH7900`/`ITECH6006` patterns.
3. Wire into `InstrumentManager.initialize_instruments` and `health_report`.
4. Update config/profile addresses.

### Add a New Sequencer Action
1. Extend `Sequencer._execute_action` with a new branch.
2. Call into CANManager/InstrumentManager/driver with parameters parsed from `params`.
3. Return `(success: bool, message: str)`; emit any intermediate info via `action_info`.

### Add a New CAN Test Method
1. Implement method in `CANManager` with timeout/tolerance handling.
2. Expose via Sequencer under `CAN / ...`.
3. (Optional) Add a UI dialog in Dashboard to collect params.

### Add a UI Control
1. Modify `Dashboard` (for config/sequence) or `MainWindow` (for tabs/tools).
2. Connect signals to handlers in `MainWindow`.
3. If heavy, consider lazy-loading like the Data/Instrument tabs.

---

## 33) SCPI Command Summary (Per Driver)

### ITECH6006 (PS)
- Set: `VOLT {v}`, `CURR {c}`
- Measure: `MEAS:VOLT?`, `MEAS:CURR?`
- Power: `OUTP ON|OFF`
- Errors: `SYST:ERR?`, `SYST:ERR:CLEAR`
- Ramps/Sweeps: implemented in Python loops (no SCPI aggregate ramp beyond simple sets).

### ITECH7900 (Grid)
- Set: `VOLT {v}`, `CURR {c}`, `FREQ {f}`
- Measure: `MEAS:VOLT?`, `MEAS:CURR?`, `MEAS:FREQ?`
- Power: `OUTP ON|OFF`
- THD/Power: `MEAS:POW:REAL?`, `MEAS:POW:REAC?`, `MEAS:POW:APP?`, `MEAS:CURR:HARMonic:THD?`, `MEAS:VOLT:HARMonic:THD?`
- Reset: `*RST` (via `reset_system` in Sequencer).

### SiglentSDX (Scope)
- Run: `TRMD AUTO`
- Stop: `STOP`
- Waveform: `C1:WF? DAT2`
- IDN/Health: `*IDN?`

---

## 34) CAN Log Formats (Details)

- **CSV** (`Test Results/trace_<ts>.csv`):
  - Columns: Time (ms, relative), Type (Rx/Tx), ID (hex), DLC, Data (space-separated hex bytes).
- **TRC** (`Test Results/trace_<ts>.trc`):
  - Lines: `<counter>)  DT  <time_ms>  <ID>  <Rx|Tx>  <DLC>  <Data bytes>`
- Start/stop logging via `CANManager.start_logging/stop_logging` (UI buttons or Sequencer actions).

---

## 35) Safety & Preflight (Operational Guidance)

- Always connect CAN (UI: “Connect CAN”) and run Tools → Check Instrument Health before starting sequences.
- E-Stop is available in the Dashboard to halt sequence, stop cyclic CAN, and power down PS/Grid.
- Use simulation profile (`sim`) when hardware is not connected.
- Preflight enforced in `MainWindow.on_run_sequence`: blocks run if CAN disconnected or any instrument health is not OK.

---

## 36) Troubleshooting (Expanded)

- **CAN not connected**: Connect via Dashboard; re-run preflight.
- **Instrument health fail**: Check device connectivity, addresses in profile/config, and rerun Tools → Check Instrument Health.
- **PyInstaller missing**: Call full path (e.g., `$env:APPDATA\\Python\\Python314\\Scripts\\pyinstaller.exe`) or add to PATH.
- **Sequence stops early**: Inspect Output log for failing step message; Sequencer stops on first failure.
- **Trace not recording**: Ensure CAN connected; Start Trace creates files in `Test Results`.
- **UI sluggish**: Data/Instrument tabs are lazy-loaded; avoid opening heavy tabs unless needed.

---

## 37) Deployment Checklist

- Dependencies: install from `requirements.txt`.
- Verify `DBC/` and `CAN Configuration/` present.
- Verify `Test Sequence/` writable for saves.
- Run `python -m unittest discover tests`.
- Build (optional): PyInstaller command (see section 28).
- Distribute `dist/AtomX/` bundle with required data folders.

---

## 38) Future Improvements (Recommended)

- DataDashboard: configurable layouts/thresholds; trend charts with alerts.
- Oscilloscope: richer SCPI control (channels, scaling, acquisition, screenshots).
- Sequencer: branching/loop constructs; async/cancellable actions.
- CAN: per-signal thresholds and alerting; GUI-driven cyclic definitions.
- Logging: structured step logs (JSON) and optional HTML/PDF report generator.
- Safety: configurable soft limits for PS/Grid setpoints; confirmation dialogs for high-risk actions.

---

## 39) Action Parameter Reference (UI Dialog Ranges – Code-Verified)

- CAN / Read Signal Value:
  - Signal (text, required), Timeout (0.1–60 s)
- CAN / Check Signal (Tolerance):
  - Signal (text), Expected (±10000, decimals=3), Tolerance (0–10000, decimals=3), Timeout (0.1–60 s)
- CAN / Conditional Jump:
  - Signal (text), Expected (±10000), Tolerance (0–10000, default 0.1), Jump Step (1–9999)
- CAN / Wait For Signal Change:
  - Signal (text), Initial (±10000, decimals=3), Timeout (0.1–60 s), Poll Interval (0.01–5 s)
- CAN / Monitor Signal Range:
  - Signal (text), Min/Max (±10000, decimals=3), Duration (0.1–300 s), Poll Interval (0.1–10 s)
- CAN / Compare Two Signals:
  - Signal1/Signal2 (text), Tolerance (0–10000, decimals=3), Timeout (0.1–60 s)
- CAN / Set Signal and Verify:
  - Message ID (0–0x7FF), Signal (text), Target (±10000, decimals=3), Tolerance (0–10000, decimals=3), Verify Timeout (0.1–60 s)
- PS / Battery Set Charge/Discharge:
  - Voltage/Current (spin boxes in dialog)
- Ramp dialogs (GS/PS):
  - Start/End (±10000), Step (0.0001–10000), Delay (0–3600), Tolerance (0–1000), Retries (0–100)
- Wait action:
  - Params is a float/str for seconds in Sequencer (`Wait: <seconds>`).

---

## 40) File & Directory Conventions (Code-Verified)

- Sequences: `Test Sequence/*.json` (meta+steps) or legacy list format.
- CAN traces: `Test Results/trace_<YYYYMMDD_HHMMSS>.csv|.trc`.
- Logs: `logs/app.log` (rotating JSON).
- DBC: `DBC/RE.dbc` (loaded by default).
- CAN config: `CAN Configuration/` (e.g., `can_messages.py`, `signal_mapping.json`).
- Docs: `docs/` (manuals, CLI guide).
- Executable build output (when using PyInstaller): `dist/AtomX/`.

---

## 41) Release Notes Template (Fill Per Version)

- Version:
- Date:
- Changes:
  - Features:
  - Fixes:
  - Safety:
  - Compatibility:
- Known Issues:
- Upgrade Notes:
- Validation:
  - Tests run (unit/CLI/GUI smoke):
  - Hardware tested (profiles):
- Packaging:
  - PyInstaller build: (yes/no)
  - Included assets: DBC, CAN Configuration, Test Sequence

---

## 42) Extension Checklist (Practical Steps)

- New instrument:
  - Implement driver interface (driver_base).
  - Add SCPI methods; implement `health_check`.
  - Wire into `InstrumentManager.initialize_instruments` and `health_report`.
- New CAN action:
  - Add method to `CANManager`; expose in `Sequencer._execute_action`.
  - (Optional) Add UI dialog for parameters.
- New UI control/tab:
  - Add widget to Dashboard or `MainWindow`; connect signals; lazy-load if heavy.
- New sequence behavior:
  - Extend `Sequencer._execute_action`; ensure `(bool, message)` returns; stop on failure semantics preserved.
- Logging:
  - Use `logger.log(level, message)` via injected logger; keep CSV/TRC for CAN only in `CANManager`.

---

## 43) Operational Safety Notes (Enforced in Code)

- Preflight before run: requires CAN connected and all instruments healthy; otherwise run is blocked with a warning.
- E-Stop: halts sequence, stops cyclic CAN, powers down PS/Grid (best-effort) and logs warning.
- Simulation profile: use when hardware is absent to prevent SCPI/CAN side effects.
- Traces: ensure CAN is connected before starting trace to avoid empty files.

---

## 44) Action-to-Backend Mapping (Code-Verified)

- `CAN / Connect` → `CANManager.connect()`
- `CAN / Disconnect` → `CANManager.disconnect()`
- `CAN / Start Cyclic CAN` → `CANManager.start_all_cyclic_messages()`
- `CAN / Stop Cyclic CAN` → `CANManager.stop_all_cyclic_messages()`
- `CAN / Start Trace` → `CANManager.start_logging(...)`
- `CAN / Stop Trace` → `CANManager.stop_logging()`
- `CAN / Send Message` → `CANManager.send_message(...)`
- `CAN / Start Cyclic By Name` → `CANManager.start_cyclic_message_by_name(...)`
- `CAN / Stop Cyclic By Name` → `CANManager.stop_all_cyclic_messages()` (per config)
- `CAN / Check Message` → listener with timeout in Sequencer
- `CAN / Listen For Message` → listener with timeout in Sequencer
- CAN test actions (dialogs) → corresponding `CANManager` methods:
  - Read Signal Value → `read_signal_value`
  - Check Signal (Tolerance) → `check_signal_tolerance`
  - Conditional Jump → `conditional_jump_check`
  - Wait For Signal Change → `wait_for_signal_change`
  - Monitor Signal Range → `monitor_signal_range`
  - Compare Two Signals → `compare_two_signals`
  - Set Signal and Verify → `set_signal_and_verify`
- `GS / ...` actions → `InstrumentManager.itech7900` methods (set/get V/I/Freq, power, THD/power measures, ramps)
- `PS / ...` actions → `InstrumentManager.itech6000` methods (set/get V/I, power, ramps, sweeps, battery set charge/discharge)
- `Initialize Instruments` → `InstrumentManager.initialize_instruments()`
- `Wait` → Sequencer delay loop with responsiveness to `running` flag

---

## 45) Sequence Examples (Code-Realistic)

### Example: CAN Smoke (simulation)
```json
{
  "meta": {"name": "CAN_Smoke", "author": "QA", "version": 1},
  "steps": [
    {"action": "CAN / Connect", "params": ""},
    {"action": "CAN / Start Cyclic CAN", "params": ""},
    {"action": "CAN / Read Signal Value", "params": "{\"signal_name\": \"GridVol\", \"timeout\": 2.0}"},
    {"action": "CAN / Stop Cyclic CAN", "params": ""},
    {"action": "CAN / Disconnect", "params": ""}
  ]
}
```

### Example: PS/GS Setpoints + CAN Check
```json
{
  "meta": {"name": "PS_GS_Cycle", "author": "QA", "version": 1},
  "steps": [
    {"action": "Initialize Instruments", "params": ""},
    {"action": "CAN / Connect", "params": ""},
    {"action": "GS / Set Voltage AC", "params": "230"},
    {"action": "GS / Set Frequency", "params": "50"},
    {"action": "PS / Set Voltage", "params": "48"},
    {"action": "PS / Set Current", "params": "10"},
    {"action": "CAN / Check Signal (Tolerance)", "params": "{\"signal_name\": \"GridVol\", \"expected_value\": 230, \"tolerance\": 5, \"timeout\": 2}"},
    {"action": "CAN / Disconnect", "params": ""}
  ]
}
```

---

## 46) System Requirements (Derived from Code/Deps)

- Python: compatible with PyQt6, PyQt6-WebEngine, python-can, cantools, pyvisa, pyqtdarktheme (see `requirements.txt`).
- Runtime assets: `DBC/RE.dbc`, `CAN Configuration/`, `Test Sequence/` writable, `Test Results/` writable for traces.
- For hardware mode: reachable SCPI instruments at profile addresses; CAN interface and channel configured per profile.
- For packaging: PyInstaller (6.17.0 tested per install logs).

---

## 47) Audit Checklist (Operational & Code)

- Profiles validated (sim/dev/hw) with correct CAN/instrument addresses.
- DBC loads successfully (`Loaded DBC` message on startup).
- Instrument health passes (Tools → Check Instrument Health).
- Preflight enforced before sequences; failures block run.
- E-Stop tested: stops sequence, stops cyclic CAN, powers down PS/Grid, logs warning.
- CAN trace start/stop creates CSV/TRC in `Test Results/`.
- CLI run tested in sim profile (`run_sequence.py`).
- PyInstaller build tested (if distributing binary).

---

## 48) Known Behavior (Code-Observed)

- Sequencer stops on first failed step; no built-in retries per step.
- Ramps/sweeps are synchronous; E-Stop/stop sequence is the cancellation path.
- DataDashboard is static (signals hardcoded in `SIGNALS` list).
- Metadata dialog on save: cancel still saves using existing defaults.

---

## 49) How to Add Reporting (Guidance Based on Current Hooks)

- Use app logger in Sequencer/MainWindow to emit structured JSON per step.
- Post-process `logs/app.log` and CAN traces to build reports (external script).
- For HTML/PDF, generate from saved sequence + logs; no built-in exporter exists.

---

## 50) Headless vs GUI Equivalence

- Both GUI and CLI use the same core managers (`InstrumentManager`, `CANManager`, `Sequencer`).
- Simulation mode works in both; set `simulation_mode` in profile or use `--profile sim`.
- GUI enforces preflight and provides E-Stop; CLI currently stops on failure only (no E-Stop in CLI).

---

## 51) Quick Reference Tables (Actions & Params)

| Action (Sequencer) | Params | Backend | Notes |
|--------------------|--------|---------|-------|
| CAN / Connect | "" | CANManager.connect | Uses profile defaults |
| CAN / Disconnect | "" | CANManager.disconnect | Stops notifier/bus |
| CAN / Start Cyclic CAN | "" | CANManager.start_all_cyclic_messages | Uses `can_messages.py` |
| CAN / Stop Cyclic CAN | "" | CANManager.stop_all_cyclic_messages | Stops all periodic TX |
| CAN / Start Trace | "" | CANManager.start_logging | Creates CSV/TRC in Test Results |
| CAN / Stop Trace | "" | CANManager.stop_logging | Closes files |
| CAN / Send Message | JSON or ID,data | Sequencer → CANManager.send_message | Accepts JSON or comma-separated |
| CAN / Read Signal Value | JSON (signal, timeout) | CANManager.read_signal_value | Dialog-enforced |
| CAN / Check Signal (Tolerance) | JSON | CANManager.check_signal_tolerance | Dialog-enforced |
| CAN / Conditional Jump | JSON | CANManager.conditional_jump_check | Dialog-enforced |
| CAN / Wait For Signal Change | JSON | CANManager.wait_for_signal_change | Dialog-enforced |
| CAN / Monitor Signal Range | JSON | CANManager.monitor_signal_range | Dialog-enforced |
| CAN / Compare Two Signals | JSON | CANManager.compare_two_signals | Dialog-enforced |
| CAN / Set Signal and Verify | JSON | CANManager.set_signal_and_verify | Dialog-enforced |
| GS / Set Voltage/Current/Freq | value | InstrumentManager.itech7900 | SCPI VOLT/CURR/FREQ |
| GS / Measure Voltage/Current/Freq | "" | InstrumentManager.itech7900 | SCPI MEAS:* |
| GS / Power: ON/OFF | "" | InstrumentManager.itech7900 | SCPI OUTP |
| GS / Ramp Up/Down Voltage | JSON | Sequencer loop calling set/get | Closed-loop verify |
| PS / Set Voltage/Current | value | InstrumentManager.itech6000 | SCPI VOLT/CURR |
| PS / Output ON/OFF | "" | InstrumentManager.itech6000 | SCPI OUTP |
| PS / Ramp Up/Down Voltage | JSON | Sequencer loop calling set/get | Closed-loop verify |
| PS / Battery Set Charge/Discharge | JSON | InstrumentManager.itech6000 | Set V/I then OUTP ON |
| Wait | seconds | Sequencer wait loop | Responsive to stop flag |
| Initialize Instruments | "" | InstrumentManager.initialize_instruments | Connects all |
| E-Stop | n/a | MainWindow.on_estop | Stop sequence + cyclic + power down |

---

## 52) GUI Workflows (Step-by-Step)

**Connect & Trace**  
1. Open Configuration tab.  
2. Click “Connect CAN”.  
3. Optional: “Start Cyclic CAN”.  
4. Click “Start Trace” to record CSV/TRC.  
5. Click “Stop Trace” to end.  
6. “Disconnect CAN”.

**Run a Sequence (with preflight)**  
1. Ensure instruments initialized (Dashboard → Initialize Instruments).  
2. Connect CAN.  
3. Build steps in sequence table or load a sequence.  
4. Click “Run Sequence”. Preflight enforces CAN + instrument health.  
5. Monitor Output log and table statuses.  
6. If needed, click “E-Stop” to halt and power down.

**Check Instrument Health**  
1. Go to Tools tab.  
2. Click “Check Instrument Health”.  
3. View ✓/✗ messages in Output log.

**Save Sequence with Metadata**  
1. Click “Save Sequence”.  
2. “Test Details” popup: Name/Author/Description/Tags (optional).  
3. OK saves with entered values; Cancel saves with defaults.

---

## 53) CLI Workflows (Headless)

**Simulation run**  
```bash
python run_sequence.py --sequence "Test Sequence/sequence.json" --profile sim
```

**Hardware run with init**  
```bash
python run_sequence.py --sequence "Test Sequence/sequence.json" --profile hw --init-instruments
```

**Debug logging**  
```bash
python run_sequence.py --sequence "Test Sequence/sequence.json" --profile sim --log-level DEBUG
```

Notes: CLI stops on step failure; no E-Stop hook in CLI; uses same Sequencer/Managers as GUI.

---

## 54) Preflight & E-Stop Behavior (Technical Detail)

- Preflight (MainWindow.on_run_sequence):
  - Fails if `CANManager.is_connected` is False.
  - Fails if any `HealthStatus.ok` from `InstrumentManager.health_report()` is False.
  - On failure: writes to Output log, logs ERROR, shows QMessageBox warning; run aborted.
- E-Stop (MainWindow.on_estop):
  - Calls `sequencer.stop_sequence()`.
  - Calls `can_mgr.stop_all_cyclic_messages()` (best-effort).
  - Calls `inst_mgr.safe_power_down()` (best-effort OUTP OFF on PS/Grid).
  - Logs warning to Output and logger.

---

## 55) Data Flow (High-Level)

- DBC load → `CANManager._initialize_message_definitions` → `signal_cache` seeded.
- CAN Rx (bus or simulation) → `_on_message_received` → decode → `_cache_signals` → listeners notified → `SignalManager.process_can_message` (if used) → DataDashboard reads cache on timer.
- Sequence run → Sequencer dispatch → CANManager/InstrumentManager actions → messages/status emitted to Dashboard (Output log + table) → logger writes JSON log.
- Trace → CANManager `_log_message` → CSV/TRC written in `Test Results/`.

---

## 56) Threading Model

- Sequencer runs on a worker thread; `running` flag used for stop/E-Stop.
- CANManager:
  - `can.Notifier` callback for live RX.
  - Simulation thread (`_simulate_traffic`) when in simulation mode.
- UI: main Qt thread; dashboards and dialogs operate on Qt events; periodic updates via QTimer (DataDashboard).

---

## 57) Error Handling (Patterns)

- Most methods return `(bool, message)` (CAN, instruments, Sequencer actions).
- Sequencer stops on first failure; logs message; updates status to Fail.
- CAN connect failures log and return False; disconnect swallows errors.
- E-Stop ignores secondary errors during shutdown; logs warning.
- Preflight shows a blocking warning dialog if failing conditions detected.

---

## 58) Metrics & Diagnostics

- `CANManager.get_diagnostics`: connection status, rx/tx counts, error_count, cache sizes, listeners, DBC loaded.
- `CANManager.print_diagnostics`: formatted console output.
- Message history: keeps last `max_history_size` (default 100) decoded entries.

---

## 59) Packaging Reminders

- Include data folders: `DBC`, `CAN Configuration`, `Test Sequence` in PyInstaller build (`--add-data`).
- Ensure Qt plugins are auto-bundled (PyQt6).
- Test the built binary: connect CAN (or sim), run a short sequence, start/stop trace.

---

## 60) Roadmap Anchors (Next Steps to Consider)

- Add configurable soft limits and confirmations for PS/Grid setpoints.
- Add CLI E-Stop or step retry logic.
- Expand oscilloscope SCPI coverage.
- Add per-signal thresholds/alerts in DataDashboard with configurable layout.
- Add branching/looping in Sequencer with condition objects rather than string parsing.

---
