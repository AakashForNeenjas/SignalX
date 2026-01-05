import time
from .base import StepExecutor


class StabilityMonitor(StepExecutor):
    """
    Monitor one or more messages for a duration, ensuring no gap exceeds max_gap_ms.
    Params:
      - message_ids: list of arbitration IDs (int or hex str)
      - duration_ms: total monitoring duration
      - max_gap_ms: maximum allowed gap between frames (default 500 ms)
    """

    def execute(self, step, ctx):
        if not ctx.metrics:
            return False, "Metrics not available"
        msg_ids = step.params.get("message_ids", [])
        duration_ms = step.params.get("duration_ms", 5000)
        max_gap = step.params.get("max_gap_ms", 500)
        # normalize ids
        norm_ids = []
        for mid in msg_ids:
            try:
                norm_ids.append(int(mid, 0) if isinstance(mid, str) else int(mid))
            except Exception:
                pass
        start = time.time()
        violations = []
        while (time.time() - start) * 1000.0 < duration_ms:
            for mid in norm_ids:
                gap = ctx.metrics.time_since_last_ms(mid)
                if gap is None:
                    violations.append(f"id {hex(mid)} no frames seen")
                elif gap > max_gap:
                    violations.append(f"id {hex(mid)} gap {gap:.1f}ms > {max_gap}ms")
            if violations:
                return False, "; ".join(violations)
            time.sleep(0.05)
        return True, f"Stability ok for {len(norm_ids)} ids over {duration_ms} ms"
