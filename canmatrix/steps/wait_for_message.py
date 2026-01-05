import threading
import time
from .base import StepExecutor


class WaitForMessage(StepExecutor):
    """
    Wait for a specific CAN message (by name or arbitration_id) to arrive.
    Uses CANManager listeners so decoded signals land in the shared signal_cache.
    """

    def execute(self, step, ctx):
        msg_name = step.params.get("message")
        arb_id = step.params.get("arbitration_id")
        timeout_ms = step.params.get("timeout_ms", 2000)
        expected_dlc = step.params.get("expected_dlc")

        if not ctx.can_mgr:
            return False, "CAN manager not available"
        if hasattr(ctx.can_mgr, "is_connected") and not ctx.can_mgr.is_connected:
            return False, "CAN not connected"
        if not msg_name and arb_id is None:
            return False, "Message name or arbitration_id required"

        # Resolve arbitration id from DBC if name provided
        if msg_name and ctx.dbc_mgr and getattr(ctx.dbc_mgr, "db", None):
            try:
                message_def = ctx.dbc_mgr.db.get_message_by_name(msg_name)
                arb_id = message_def.frame_id
            except Exception:
                pass

        if arb_id is None:
            return False, f"Could not resolve arbitration id for {msg_name}"

        received = {"msg": None}
        evt = threading.Event()

        def _listener(msg):
            try:
                if msg.arbitration_id == arb_id:
                    received["msg"] = msg
                    evt.set()
            except Exception:
                pass

        ctx.can_mgr.add_listener(_listener)
        ok = evt.wait(timeout_ms / 1000.0)
        try:
            ctx.can_mgr.remove_listener(_listener)
        except Exception:
            pass

        if not ok:
            return False, f"Timeout waiting for message {msg_name or hex(arb_id)}"

        if expected_dlc is not None and hasattr(received["msg"], "dlc"):
            if received["msg"].dlc != expected_dlc:
                return False, f"Message {msg_name or hex(arb_id)} DLC mismatch (got {received['msg'].dlc}, expected {expected_dlc})"

        return True, f"Received message {msg_name or hex(arb_id)}"
