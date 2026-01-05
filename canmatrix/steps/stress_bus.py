import time
from .base import StepExecutor


class StressBus(StepExecutor):
    """
    Simple bus load generator: sends one or more frames repeatedly for a duration.
    Params:
      - frames: list of {id, data, period_ms}; if empty, uses default filler frame 0x7FF with zeros
      - duration_ms: total duration
    """

    def execute(self, step, ctx):
        if not ctx.can_mgr:
            return False, "CAN manager not available"
        frames = step.params.get("frames", [])
        duration_ms = step.params.get("duration_ms", 500)
        start = time.time()
        if not frames:
            frames = [{"id": 0x7FF, "data": [0x00], "period_ms": 1.0}]
        next_send = [start + (f.get("period_ms", 1.0) / 1000.0) for f in frames]
        try:
            while (time.time() - start) * 1000.0 < duration_ms:
                now = time.time()
                for idx, f in enumerate(frames):
                    if now >= next_send[idx]:
                        arb_id = int(f.get("id", 0x7FF))
                        data = f.get("data", [0x00])
                        ctx.can_mgr.send_message(arb_id, data, is_extended_id=False)
                        period = f.get("period_ms", 1.0) / 1000.0
                        next_send[idx] = now + period
                time.sleep(0.0005)
        except Exception as e:
            return False, f"Stress failed: {e}"
        return True, f"Stress run {duration_ms} ms with {len(frames)} frame(s)"
