
class CanInterface:
    """Adapter over existing CANManager instance."""

    def __init__(self, can_mgr):
        self.can_mgr = can_mgr

    def send_frame(self, frame_id, data, is_extended=False):
        self.can_mgr.send_message(frame_id, list(data), is_extended)

    def start_cyclic(self, frame_id, data, period_ms, is_extended=False):
        # reuse CANManager start_cyclic_message if available
        return self.can_mgr.start_cyclic_message(frame_id, list(data), period_ms / 1000.0, is_extended_id=is_extended)

    def stop_cyclic(self, frame_id):
        try:
            self.can_mgr.stop_cyclic_message(frame_id)
        except Exception:
            pass

    def is_connected(self):
        return getattr(self.can_mgr, "is_connected", False)
