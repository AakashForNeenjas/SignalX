
from .base import StepExecutor


class StartCyclic(StepExecutor):
    def execute(self, step, ctx):
        msg_name = step.params.get("message")
        signals = step.params.get("signals", {})
        period_ms = step.params.get("period_ms", 100)
        if not msg_name:
            return False, "Missing message name"
        try:
            frame_id, data, is_ext = ctx.dbc.encode(msg_name, signals)
            ctx.can.start_cyclic(frame_id, data, period_ms, is_ext)
            ctx.log.info(f"CMD: START_CYCLIC {msg_name} id=0x{frame_id:X} period={period_ms}ms")
            return True, f"Cyclic {msg_name} started"
        except Exception as e:
            return False, f"StartCyclic failed: {e}"
