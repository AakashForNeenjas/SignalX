# AtomX Developer Setup Guide

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Development Environment Setup](#development-environment-setup)
3. [Running the Application](#running-the-application)
4. [Running Tests](#running-tests)
5. [Code Quality Tools](#code-quality-tools)
6. [Project Structure](#project-structure)
7. [Development Workflow](#development-workflow)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Software
- **Python 3.14+**: Download from [python.org](https://www.python.org/)
- **Git**: Version control system
- **PCAN Driver**: For CAN interface (if using hardware)
- **NI-VISA**: For instrument control (if using hardware)

### Hardware (Optional)
- PEAK PCAN-USB adapter
- ITECH 6006 Power Supply
- ITECH 7900 Grid Emulator
- Siglent SDX Oscilloscope
- Maynuo M97 DC Load

**Note**: All hardware is optional. The application fully supports simulation mode for development without physical hardware.

## Development Environment Setup

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/atomx.git
cd atomx
```

### 2. Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
# Install all dependencies
pip install -r requirements.txt

# Verify installation
pip list
```

### 4. Configure Environment Variables (Optional)

Create a `.env` file in the project root:

```bash
# Instrument addresses
ATOMX_PS_ADDRESS=TCPIP::192.168.4.53::INSTR
ATOMX_GS_ADDRESS=TCPIP::192.168.4.52::INSTR
ATOMX_OS_ADDRESS=TCPIP::192.168.4.51::INSTR
ATOMX_LOAD_PORT=COM3

# CAN configuration
ATOMX_CAN_INTERFACE=pcan
ATOMX_CAN_CHANNEL=PCAN_USBBUS1
ATOMX_CAN_BITRATE=500000
```

### 5. Verify Setup

```bash
# Check Python version
python --version  # Should be 3.14+

# Check imports
python -c "import PyQt6; import can; import pyvisa; print('Setup OK')"
```

## Running the Application

### Development Mode

```bash
# From project root
python main.py
```

### Simulation Mode

The application starts in simulation mode by default (no hardware required).

To switch to hardware mode:
1. Launch application
2. Go to Config tab
3. Select a hardware profile (lab_a, lab_b, etc.)

### Debug Mode

```bash
# Enable verbose logging
python main.py --log-level DEBUG
```

## Running Tests

### Quick Test

```bash
# Run all tests
pytest

# Run with output
pytest -v
```

### Unit Tests Only

```bash
pytest tests/unit/
```

### Integration Tests

```bash
pytest tests/integration/
```

### Coverage Report

```bash
# Generate HTML coverage report
pytest --cov=core --cov=ui --cov-report=html

# View report
# Open htmlcov/index.html in browser
```

### Watch Mode

```bash
# Install pytest-watch
pip install pytest-watch

# Run tests on file changes
ptw
```

### Test Specific Module

```bash
pytest tests/unit/can/test_simulation.py
pytest tests/unit/can/test_logging.py -v
```

### Run Tests with Markers

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Skip slow tests
pytest -m "not slow"

# Run simulation tests only
pytest -m simulation
```

## Code Quality Tools

### Type Checking with MyPy

```bash
# Check all files
mypy .

# Check specific module
mypy core/can/

# Strict mode
mypy --strict core/can/simulation.py
```

### Code Formatting with Black

```bash
# Format all files
black .

# Check without modifying
black --check .

# Format specific file
black core/CANManager.py
```

### Linting with Flake8

```bash
# Lint all files
flake8 .

# Lint specific directory
flake8 core/

# Generate report
flake8 --output-file=flake8-report.txt
```

### Code Analysis with Pylint

```bash
# Analyze code
pylint core/

# Generate report
pylint core/ > pylint-report.txt
```

### Run All Quality Checks

```bash
# Create a script or run manually
black . && flake8 . && mypy . && pytest
```

## Project Structure

```
AtomX/
├── main.py                 # Application entry point
├── config.py               # Configuration
├── config_loader.py        # Profile management
├── requirements.txt        # Dependencies
├── pytest.ini              # Pytest configuration
├── mypy.ini                # MyPy configuration
│
├── core/                   # Business logic
│   ├── CANManager.py
│   ├── InstrumentManager.py
│   ├── Sequencer.py
│   ├── can/                # Modular CAN components
│   │   ├── __init__.py
│   │   ├── simulation.py
│   │   ├── connection.py
│   │   ├── cyclic.py
│   │   ├── logging.py
│   │   └── signals.py
│   ├── instruments/        # Instrument drivers
│   └── actions/            # Sequence actions
│
├── ui/                     # User interface
│   ├── MainWindow.py
│   ├── Dashboard.py
│   └── widgets/
│
├── tests/                  # Test suite
│   ├── conftest.py         # Pytest fixtures
│   ├── unit/               # Unit tests
│   │   └── can/
│   │       ├── test_simulation.py
│   │       ├── test_logging.py
│   │       └── test_connection.py
│   └── integration/        # Integration tests
│
├── docs/                   # Documentation
│   ├── architecture/       # Architecture docs
│   └── DEVELOPER_SETUP.md  # This file
│
├── DBC/                    # CAN database files
├── CAN Configuration/      # CAN message configs
├── logs/                   # Application logs
└── Test Results/           # Test output files
```

## Development Workflow

### 1. Create Feature Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Write Tests First (TDD)

```python
# tests/unit/test_your_feature.py
import pytest
from core.your_module import YourClass

@pytest.mark.unit
def test_your_feature():
    obj = YourClass()
    result = obj.your_method()
    assert result == expected_value
```

### 3. Implement Feature

```python
# core/your_module.py
from typing import Optional

class YourClass:
    def your_method(self) -> Optional[str]:
        """Your method documentation.

        Returns:
            Optional string result
        """
        return "result"
```

### 4. Run Tests

```bash
pytest tests/unit/test_your_feature.py -v
```

### 5. Check Code Quality

```bash
# Format code
black core/your_module.py

# Type check
mypy core/your_module.py

# Lint
flake8 core/your_module.py
```

### 6. Commit Changes

```bash
git add .
git commit -m "feat: add your feature description"
```

### 7. Push and Create PR

```bash
git push origin feature/your-feature-name
# Create PR on GitHub
```

## Common Development Tasks

### Add a New CAN Module

1. Create module in `core/can/your_module.py`
2. Add type hints and docstrings
3. Create tests in `tests/unit/can/test_your_module.py`
4. Update `core/can/__init__.py` exports
5. Run: `pytest tests/unit/can/test_your_module.py`

### Add a New Instrument Driver

1. Create driver in `core/instruments/your_instrument.py`
2. Inherit from `VisaInstrument` base class
3. Implement required methods
4. Add to InstrumentManager
5. Create unit tests

### Add a New Sequence Action

1. Create action in `core/actions/your_action.py`
2. Add schema to `core/action_schemas.py`
3. Register in Sequencer
4. Create integration test
5. Update `docs/ACTION_DEFINITIONS.json`

## Troubleshooting

### Import Errors

```bash
# Ensure virtual environment is activated
which python  # Should show venv path

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### PyQt6 Issues

```bash
# Windows: Install Visual C++ Redistributable
# Linux: Install Qt6 dependencies
sudo apt-get install qt6-base-dev

# Reinstall PyQt6
pip uninstall PyQt6
pip install PyQt6==6.10.0
```

### CAN Bus Connection Fails

```bash
# Check PCAN driver
# Windows: Run PCAN-View to verify hardware

# Check permissions
# Linux: Add user to dialout group
sudo usermod -a -G dialout $USER

# Use simulation mode for development
# No hardware required
```

### VISA Instrument Connection Fails

```bash
# Install NI-VISA Runtime
# Download from ni.com

# Or use PyVISA-py backend
pip install pyvisa-py
export PYVISA_LIBRARY=@py

# Use simulation mode
# No instruments required
```

### Test Failures

```bash
# Run with verbose output
pytest -vv

# Run specific test
pytest tests/unit/can/test_simulation.py::TestCANSimulator::test_init -v

# Check for updated dependencies
pip list --outdated
```

### Coverage Not Generated

```bash
# Install pytest-cov
pip install pytest-cov

# Run with coverage
pytest --cov=core --cov-report=html

# Check htmlcov/index.html
```

## IDE Setup

### VS Code

Install extensions:
- Python
- Pylance
- Python Test Explorer
- mypy

Settings (`.vscode/settings.json`):
```json
{
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.linting.mypyEnabled": true,
    "python.formatting.provider": "black",
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": ["tests"]
}
```

### PyCharm

1. Set Python interpreter to venv
2. Enable pytest as test runner
3. Configure mypy as external tool
4. Enable Black formatter

## Getting Help

### Resources
- **Architecture Docs**: [docs/architecture/ARCHITECTURE.md](architecture/ARCHITECTURE.md)
- **API Docs**: Generated with `pdoc`
- **Issue Tracker**: GitHub Issues
- **Logs**: `logs/app.log`

### Common Commands Reference

```bash
# Development
python main.py                          # Run application
pytest                                  # Run tests
pytest --cov=core                       # Run with coverage
black .                                 # Format code
mypy .                                  # Type check
flake8 .                                # Lint code

# Git
git status                              # Check status
git checkout -b feature/name            # New branch
git add .                               # Stage changes
git commit -m "message"                 # Commit
git push origin feature/name            # Push branch

# Virtual Environment
python -m venv venv                     # Create venv
venv\Scripts\activate                   # Activate (Windows)
source venv/bin/activate                # Activate (Linux/Mac)
deactivate                              # Deactivate
```

---

**Happy Coding!**

For questions or issues, please contact the development team or file an issue on GitHub.
