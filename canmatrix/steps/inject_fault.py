import time
import random
from .base import StepExecutor


class InjectFault(StepExecutor):
    """
    Inject fault conditions on the bus:
    modes: wrong_id, wrong_dlc, corrupt_payload, burst, back_to_back
    Params:
      - target_id (int, hex str)
      - data (list[int] or bytes), dlc (int)
      - count (int) for burst/back_to_back
      - spacing_ms (float) for back_to_back/burst
    """

    def execute(self, step, ctx):
        if not ctx.can_mgr:
            return False, "CAN manager not available"
        mode = step.params.get("mode", "wrong_dlc")
        target_id = step.params.get("target_id", 0x7FF)
        data = step.params.get("data", [0x00])
        dlc = step.params.get("dlc", len(data))
        count = step.params.get("count", 3)
        spacing_ms = step.params.get("spacing_ms", 1.0)
        try:
            arb_id = int(target_id, 0) if isinstance(target_id, str) else int(target_id)
        except Exception:
            arb_id = 0x7FF

        def _send(id_, dlc_override=None, payload_override=None):
            payload = payload_override if payload_override is not None else data
            try:
                ctx.can_mgr.send_message(id_, payload, is_extended_id=False)
            except Exception:
                pass

        if mode == "wrong_id":
            _send(arb_id ^ 0x10, dlc_override=dlc)
            return True, f"Sent wrong-id frame {hex(arb_id ^ 0x10)}"

        if mode == "wrong_dlc":
            bad_dlc = max(0, min(8, dlc - 1))
            _send(arb_id, dlc_override=bad_dlc)
            return True, f"Sent wrong-DLC frame id={hex(arb_id)} dlc={bad_dlc}"

        if mode == "corrupt_payload":
            corrupt = list(data)
            if corrupt:
                idx = random.randrange(len(corrupt))
                corrupt[idx] ^= 0xFF
            _send(arb_id, payload_override=corrupt)
            return True, f"Sent corrupt payload frame id={hex(arb_id)}"

        if mode == "burst":
            for _ in range(max(1, count)):
                _send(arb_id, payload_override=data)
                time.sleep(spacing_ms / 1000.0)
            return True, f"Burst sent {count} frames id={hex(arb_id)}"

        if mode == "back_to_back":
            for _ in range(max(1, count)):
                _send(arb_id, payload_override=data)
                time.sleep(max(0.0, spacing_ms) / 1000.0)
            return True, f"Back-to-back {count} frames id={hex(arb_id)}"

        return False, f"Unknown fault mode {mode}"
