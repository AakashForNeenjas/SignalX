from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class HealthStatus:
    ok: bool
    message: str = ""


class PowerSupplyDriver(ABC):
    """Interface for power supply devices."""

    @abstractmethod
    def connect(self) -> tuple[bool, str]:
        ...

    @abstractmethod
    def disconnect(self) -> None:
        ...

    @abstractmethod
    def set_voltage(self, voltage: float) -> None:
        ...

    @abstractmethod
    def set_current(self, current: float) -> None:
        ...

    @abstractmethod
    def get_voltage(self) -> float:
        ...

    @abstractmethod
    def get_current(self) -> float:
        ...

    @abstractmethod
    def power_on(self) -> None:
        ...

    @abstractmethod
    def power_off(self) -> None:
        ...

    @abstractmethod
    def health_check(self) -> HealthStatus:
        ...


class GridEmulatorDriver(ABC):
    """Interface for grid emulator devices."""

    @abstractmethod
    def connect(self) -> tuple[bool, str]:
        ...

    @abstractmethod
    def disconnect(self) -> None:
        ...

    @abstractmethod
    def set_grid_voltage(self, voltage: float) -> None:
        ...

    @abstractmethod
    def set_grid_current(self, current: float) -> None:
        ...

    @abstractmethod
    def set_grid_frequency(self, freq: float) -> None:
        ...

    @abstractmethod
    def get_grid_voltage(self) -> float:
        ...

    @abstractmethod
    def get_grid_current(self) -> float:
        ...

    @abstractmethod
    def get_grid_frequency(self) -> float:
        ...

    @abstractmethod
    def power_on(self) -> None:
        ...

    @abstractmethod
    def power_off(self) -> None:
        ...

    @abstractmethod
    def health_check(self) -> HealthStatus:
        ...


class OscilloscopeDriver(ABC):
    """Interface for oscilloscope devices."""

    @abstractmethod
    def connect(self) -> tuple[bool, str]:
        ...

    @abstractmethod
    def disconnect(self) -> None:
        ...

    @abstractmethod
    def health_check(self) -> HealthStatus:
        ...
