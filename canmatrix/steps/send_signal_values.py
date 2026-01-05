
from .base import StepExecutor


class SendSignalValues(StepExecutor):
    def execute(self, step, ctx):
        msg_name = step.params.get("message")
        signals = step.params.get("signals", {})
        if not msg_name:
            return False, "Missing message name"
        try:
            frame_id, data, is_ext = ctx.dbc.encode(msg_name, signals)
            ctx.can.send_frame(frame_id, data, is_ext)
            ctx.log.info(f"CMD: SEND_SIGNAL_VALUES {msg_name} id=0x{frame_id:X} signals={signals}")
            return True, f"Sent {msg_name}"
        except Exception as e:
            return False, f"SendSignalValues failed: {e}"
