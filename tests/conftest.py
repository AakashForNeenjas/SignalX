"""Pytest configuration and fixtures for AtomX tests."""

import logging
import os
import sys
import threading
from unittest.mock import Mock, MagicMock
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session")
def qt_app():
    """Fixture providing a QApplication instance for PyQt tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def mock_dbc_parser():
    """Fixture providing a mock DBC parser."""
    parser = Mock()
    parser.database = Mock()

    # Mock message definition
    mock_message = Mock()
    mock_message.name = "TestMessage"
    mock_message.frame_id = 0x100
    mock_message.is_extended_frame = False
    mock_message.signals = []
    mock_message.encode = Mock(return_value=b'\x00\x00\x00\x00\x00\x00\x00\x00')

    parser.database.get_message_by_name = Mock(return_value=mock_message)

    return parser


@pytest.fixture
def mock_can_bus():
    """Fixture providing a mock CAN bus."""
    bus = Mock()
    bus.send = Mock()
    bus.send_periodic = Mock(return_value=Mock())
    bus.shutdown = Mock()
    return bus


@pytest.fixture
def signal_cache_lock():
    """Fixture providing a thread lock for signal cache."""
    return threading.RLock()


@pytest.fixture
def signal_cache():
    """Fixture providing an empty signal cache."""
    return {}


@pytest.fixture
def last_sent_signals():
    """Fixture providing an empty last sent signals dict."""
    return {}


@pytest.fixture
def mock_logger():
    """Fixture providing a mock logger."""
    logger = Mock(spec=logging.Logger)
    return logger


@pytest.fixture
def temp_test_dir(tmp_path):
    """Fixture providing a temporary directory for test files."""
    test_dir = tmp_path / "test_results"
    test_dir.mkdir()
    return test_dir


@pytest.fixture(autouse=True)
def reset_sys_path():
    """Reset sys.path after each test to avoid pollution."""
    original_path = sys.path.copy()
    yield
    sys.path = original_path


@pytest.fixture
def mock_message_callback():
    """Fixture providing a mock message callback function."""
    return Mock()


@pytest.fixture
def mock_log_callback():
    """Fixture providing a mock log callback function."""
    return Mock()


@pytest.fixture
def mock_diagnostics_callback():
    """Fixture providing a mock diagnostics callback function."""
    callback = Mock()
    callback.return_value = {
        'signals_with_values': 10,
        'total_messages': 100
    }
    return callback


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom settings."""
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "hardware: mark test as requiring hardware"
    )
    config.addinivalue_line(
        "markers", "simulation: mark test as using simulation mode"
    )
