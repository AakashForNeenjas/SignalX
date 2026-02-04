# AtomX Architecture Documentation

## Overview

AtomX is a comprehensive test automation framework for CAN bus signal testing and instrument control. The application is built using PyQt6 for the GUI and follows a modular architecture for maintainability and testability.

## System Architecture

```
AtomX/
├── main.py                 # Application entry point
├── core/                   # Core business logic
│   ├── CANManager.py      # CAN bus management (facade)
│   ├── InstrumentManager.py  # VISA instrument control
│   ├── Sequencer.py       # Test sequence execution
│   ├── DBCParser.py       # DBC file parsing
│   ├── SignalManager.py   # Signal mapping/management
│   ├── can/               # Modular CAN components
│   │   ├── simulation.py  # Traffic simulation
│   │   ├── connection.py  # Bus connection
│   │   ├── cyclic.py      # Periodic messages
│   │   ├── logging.py     # Message logging
│   │   └── signals.py     # Signal caching
│   ├── instruments/       # Instrument drivers
│   │   ├── base.py        # Base VISA driver
│   │   ├── itech_ps.py    # Power supply
│   │   ├── itech_grid.py  # Grid emulator
│   │   └── siglent_scope.py  # Oscilloscope
│   └── actions/           # Sequence actions
│       ├── can.py         # CAN actions
│       ├── load.py        # Load actions
│       └── ...
├── ui/                    # User interface
│   ├── MainWindow.py      # Main application window
│   ├── Dashboard.py       # Control dashboard
│   └── widgets/           # Custom widgets
├── tests/                 # Test suite
│   ├── unit/              # Unit tests
│   ├── integration/       # Integration tests
│   └── conftest.py        # Pytest fixtures
└── config.py              # Configuration management
```

## Core Components

### 1. CANManager

**Purpose**: Central facade for CAN bus communication.

**Responsibilities**:
- Connection management
- Message transmission/reception
- Signal encoding/decoding
- Message logging
- Cyclic message handling
- Traffic simulation

**Key Design Patterns**:
- **Facade Pattern**: Provides simplified interface to complex CAN subsystems
- **Observer Pattern**: Listeners for message callbacks
- **Delegation**: Delegates to specialized modules in `core/can/`

**Refactored Modules**:
```python
from core.can.simulation import CANSimulator
from core.can.connection import CANConnection
from core.can.cyclic import CyclicMessageManager
from core.can.logging import CANLogger
from core.can.signals import SignalManager
```

### 2. InstrumentManager

**Purpose**: Manages VISA instrument connections and control.

**Responsibilities**:
- Instrument initialization/disconnection
- Power supply control
- Grid emulator control
- Oscilloscope control
- DC load control

**Supported Instruments**:
- ITECH 6006 Bi-Directional Power Supply
- ITECH 7900 Grid Emulator
- Siglent SDX Oscilloscope
- Maynuo M97 DC Load

### 3. Sequencer

**Purpose**: Executes test sequences with actions.

**Responsibilities**:
- Load JSON sequence files
- Execute actions sequentially
- Handle conditional logic
- Emit progress signals
- Generate test reports

**Action Types**:
- CAN actions (send, verify, wait)
- Instrument actions (set voltage, ramp, measure)
- Load actions (set CC/CV/CP/CR, short circuit)
- Control flow (delay, loop, conditional)

### 4. UI Layer

**Purpose**: PyQt6-based graphical user interface.

**Key Components**:
- **MainWindow**: Application shell, tab management
- **Dashboard**: Real-time signal monitoring
- **SequenceTab**: Test sequence editor
- **DiagnosticsTab**: System diagnostics
- **ErrorTab**: Error injection

## Design Principles

### 1. Separation of Concerns

Each module has a single, well-defined responsibility:
- `CANManager` handles CAN communication
- `InstrumentManager` handles VISA instruments
- `Sequencer` handles test execution
- `MainWindow` handles UI presentation

### 2. Dependency Injection

Components receive their dependencies through constructor injection:
```python
sequencer = Sequencer(inst_mgr, can_mgr, logger)
```

### 3. Thread Safety

- RLock for signal cache access
- Deque for message history
- Thread-safe logging

### 4. Error Handling

- Try-except blocks with proper logging
- Graceful degradation in simulation mode
- User-friendly error messages

## Data Flow

### CAN Message Reception

```
CAN Bus → Bus Notifier → CANManager._on_message_received()
    ↓
    ├─→ DBC Decode → Signal Cache → UI Update
    ├─→ Message Logging (CSV/TRC)
    ├─→ Message History
    └─→ External Listeners
```

### Test Sequence Execution

```
User → Sequencer.start_sequence()
    ↓
    Load JSON → Parse Actions → Execute Loop
    ↓
    For each action:
        ├─→ Validate parameters
        ├─→ Execute action (CAN/Instrument/Control)
        ├─→ Emit progress signal
        └─→ Check pass/fail
    ↓
    Generate HTML Report
```

## Threading Model

### Main Thread
- PyQt event loop
- UI updates
- User interactions

### Background Threads
- CAN message reception (python-can)
- Cyclic message transmission (metrics tick)
- Traffic simulation
- Instrument operations (with timeout)

### Thread Communication
- PyQt signals/slots for thread-safe UI updates
- Locks for shared data structures
- Event objects for thread coordination

## Configuration Management

### Environment Variables

AtomX supports environment-based configuration:
```bash
ATOMX_PS_ADDRESS=TCPIP::192.168.1.100::INSTR
ATOMX_GS_ADDRESS=TCPIP::192.168.1.101::INSTR
ATOMX_CAN_INTERFACE=pcan
ATOMX_CAN_CHANNEL=PCAN_USBBUS1
```

### Profile System

Profiles allow switching between different hardware setups:
```json
{
  "profiles": {
    "sim": {"simulation_mode": true},
    "lab_a": {"instruments": {...}, "can": {...}},
    "lab_b": {"instruments": {...}, "can": {...}}
  }
}
```

## Security Considerations

### Phase 1 Security Hardening

1. **Path Traversal Prevention**
   - Input validation in `start_logging()`
   - Path normalization in `updater.py`

2. **Injection Protection**
   - Sanitized filenames (regex validation)
   - No shell command execution from user input

3. **Zip Slip Prevention**
   - Path validation during update extraction

4. **Environment-based Configuration**
   - No hardcoded credentials
   - ATOMX_* environment variables

## Testing Strategy

### Unit Tests
- Test individual modules in isolation
- Mock external dependencies
- Fast execution (<1s per test)

### Integration Tests
- Test interaction between modules
- Use real DBC files
- Test sequence execution

### Test Fixtures
```python
@pytest.fixture
def mock_dbc_parser():
    """Provides mock DBC parser."""
    ...

@pytest.fixture
def signal_cache_lock():
    """Provides thread-safe lock."""
    ...
```

## Performance Considerations

### Signal Caching
- RLock-protected dictionary
- O(1) lookups by signal name
- Timestamped entries

### Message Logging
- Buffered file I/O
- Monotonic timestamps
- Lock-protected writes

### Memory Management
- Deque with maxlen for message history
- Periodic cleanup of old cache entries

## Future Improvements

### Phase 2 Enhancements (Completed)
- ✅ Modular CAN architecture
- ✅ Comprehensive test suite
- ✅ Type hints for new modules
- ✅ MyPy configuration

### Phase 3 Roadmap
- REST API for remote control
- WebSocket for real-time monitoring
- Database for test result storage
- CI/CD pipeline integration
- Docker containerization

## Dependencies

### Core Libraries
- **PyQt6**: GUI framework
- **python-can**: CAN bus interface
- **cantools**: DBC parsing
- **PyVISA**: Instrument control
- **pandas**: Data analysis

### Testing
- **pytest**: Test framework
- **pytest-cov**: Coverage reporting
- **mypy**: Static type checking

## Development Workflow

1. **Feature Development**
   - Create feature branch
   - Write unit tests first (TDD)
   - Implement feature
   - Run tests: `pytest tests/`
   - Type check: `mypy core/`

2. **Code Quality**
   - Format: `black .`
   - Lint: `flake8 .`
   - Type check: `mypy .`

3. **Testing**
   - Unit tests: `pytest tests/unit/`
   - Integration: `pytest tests/integration/`
   - Coverage: `pytest --cov=core --cov-report=html`

4. **Documentation**
   - Update relevant .md files
   - Add docstrings to new functions
   - Update CHANGELOG.md

## Deployment

### Standalone Executable
```bash
pyinstaller AtomX.spec
```

### Development Mode
```bash
python main.py
```

## Support & Maintenance

For issues or questions:
- Check documentation in `docs/`
- Review logs in `logs/app.log`
- Submit issues on GitHub

---

**Version**: 2.4.0 (Phase 2)
**Last Updated**: 2026-01-27
**Maintained By**: AtomX Development Team
