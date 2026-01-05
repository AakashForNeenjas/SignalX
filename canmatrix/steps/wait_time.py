
import time
from .base import StepExecutor


class WaitTime(StepExecutor):
    def execute(self, step, ctx):
        ms = step.params.get("ms", 0)
        try:
            time.sleep(ms / 1000.0)
            return True, f"Waited {ms} ms"
        except Exception as e:
            return False, f"WaitTime failed: {e}"
