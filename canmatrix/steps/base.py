
from abc import ABC, abstractmethod


class StepExecutor(ABC):
    @abstractmethod
    def execute(self, step, ctx):
        """Execute step; return (success, message)."""
        raise NotImplementedError
