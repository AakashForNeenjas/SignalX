# Project Summary: AtomX

## Overview
AtomX is a comprehensive test automation framework designed for CAN bus signal testing. It provides a robust environment for defining, executing, and monitoring CAN signal tests with a focus on reliability, feedback, and ease of use.

## Key Features
- **7 Core Test Actions**:
    1. **Read Signal Value**: Read signal with timeout.
    2. **Check Signal (Tolerance)**: Validate signal within a tolerance band.
    3. **Conditional Jump**: Control flow based on signal values.
    4. **Wait For Signal Change**: Monitor for state transitions.
    5. **Monitor Signal Range**: Continuous range checking over time.
    6. **Compare Two Signals**: Verify relationships between signals.
    7. **Set Signal and Verify**: Round-trip verification of control signals.
- **Dashboard UI**: A PyQt6-based graphical interface for managing test sequences and visualizing results.
- **Robust Feedback**: Real-time diagnostics, detailed error messages, and timeout protection.
- **Production Ready**: 100% test coverage for new actions, clean architecture, and extensive documentation.

## Architecture
- **Core**: `CANManager.py` handles low-level CAN operations with timeout and polling support.
- **UI**: `Dashboard.py` and dialog classes provide the user interface for test configuration.
- **Sequencer**: `Sequencer.py` manages the execution of test steps and routing to appropriate handlers.

## Documentation
All detailed documentation has been moved to the `docs/` directory. Start with `docs/DOCUMENTATION_INDEX.md` or `docs/README.md`.
