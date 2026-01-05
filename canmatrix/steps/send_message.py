
from .base import StepExecutor


class SendMessage(StepExecutor):
    def execute(self, step, ctx):
        frame_id = step.params.get("id")
        data = step.params.get("data", [])
        is_ext = bool(step.params.get("is_extended", False))
        if frame_id is None:
            return False, "Missing frame id"
        try:
            ctx.can.send_frame(int(frame_id), data, is_ext)
            ctx.log.info(f"CMD: SEND_MESSAGE id=0x{int(frame_id):X} data={data} ext={is_ext}")
            return True, f"Sent frame 0x{int(frame_id):X}"
        except Exception as e:
            return False, f"SendMessage failed: {e}"
