
from .base import StepExecutor


class StopCyclic(StepExecutor):
    def execute(self, step, ctx):
        msg_name = step.params.get("message")
        if not msg_name:
            return False, "Missing message name"
        try:
            msg = ctx.dbc.get_message(msg_name)
            if not msg:
                return False, f"Message not found: {msg_name}"
            ctx.can.stop_cyclic(msg.frame_id)
            ctx.log.info(f"CMD: STOP_CYCLIC {msg_name} id=0x{msg.frame_id:X}")
            return True, f"Cyclic {msg_name} stopped"
        except Exception as e:
            return False, f"StopCyclic failed: {e}"
