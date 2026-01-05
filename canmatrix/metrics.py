import time
import threading
from collections import defaultdict, deque


class CanBusMetrics:
    """
    Lightweight collector that can be attached as a CANManager listener.
    Stores timestamps and DLCs per arbitration_id for interval calculations.
    """
    def __init__(self, history_size=256, dbc_mgr=None):
        self.history_size = history_size
        self.timestamps = defaultdict(lambda: deque(maxlen=history_size))
        self.dlcs = {}
        self.payloads = {}
        self.mux_seen = defaultdict(set)  # message name -> set of mux states observed
        self.dbc_mgr = dbc_mgr
        self.lock = threading.RLock()

    def attach(self, can_mgr):
        """Registers as a listener on CANManager; returns a handle to detach."""
        def _listener(msg):
            # Use a single stable clock (monotonic) for all interval calculations to avoid mixed domains
            ts = time.monotonic()
            arb = getattr(msg, "arbitration_id", None)
            dlc = getattr(msg, "dlc", None)
            data = getattr(msg, "data", None)
            if arb is None:
                return
            with self.lock:
                self.timestamps[arb].append(ts)
                if dlc is not None:
                    self.dlcs[arb] = dlc
                if data is not None:
                    self.payloads[arb] = bytes(data)
                # Multiplexer coverage collection
                if self.dbc_mgr and getattr(self.dbc_mgr, "db", None):
                    try:
                        msg_def = self.dbc_mgr.db.get_message_by_frame_id(arb)
                        if msg_def and msg_def.multiplexer_signal:
                            decoded = msg_def.decode(bytes(data))
                            mux_val = decoded.get(msg_def.multiplexer_signal.name)
                            if mux_val is not None:
                                self.mux_seen[msg_def.name].add(mux_val)
                    except Exception:
                        pass
        can_mgr.add_listener(_listener)
        return _listener

    def detach(self, can_mgr, handle):
        try:
            can_mgr.remove_listener(handle)
        except Exception:
            pass

    def last_dlc(self, arb_id):
        with self.lock:
            return self.dlcs.get(arb_id)

    def last_payload(self, arb_id):
        with self.lock:
            return self.payloads.get(arb_id)

    def last_timestamp(self, arb_id):
        with self.lock:
            ts_list = self.timestamps.get(arb_id, None)
            if not ts_list:
                return None
            return ts_list[-1]

    def mux_states(self, msg_name):
        with self.lock:
            return set(self.mux_seen.get(msg_name, set()))

    def intervals_ms(self, arb_id, window_s=10.0):
        now = time.monotonic()
        with self.lock:
            ts_list = list(self.timestamps.get(arb_id, []))
        if not ts_list:
            return []
        # filter recent
        ts_list = [t for t in ts_list if now - t <= window_s]
        if len(ts_list) < 2:
            return []
        ts_list.sort()
        return [(ts_list[i] - ts_list[i-1]) * 1000.0 for i in range(1, len(ts_list))]

    def time_since_last_ms(self, arb_id):
        with self.lock:
            ts_list = self.timestamps.get(arb_id, None)
            if not ts_list:
                return None
            last_ts = ts_list[-1]
        return (time.monotonic() - last_ts) * 1000.0
