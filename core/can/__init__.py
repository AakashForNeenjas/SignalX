"""CAN bus management modules.

This package contains modular components for CAN bus communication,
extracted from the monolithic CANManager for better maintainability.
"""

from .simulation import CANSimulator
from .connection import CANConnection
from .cyclic import CyclicMessageManager
from .logging import CANLogger
from .signals import SignalManager as CANSignalManager

__all__ = [
    'CANSimulator',
    'CANConnection',
    'CyclicMessageManager',
    'CANLogger',
    'CANSignalManager',
]
