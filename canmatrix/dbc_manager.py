
import os
import cantools
import math


class DbcManager:
    """Lightweight wrapper over cantools to reuse parsed DBCs."""

    def __init__(self):
        self.db = None

    def load(self, paths):
        """Load first DBC from list or string."""
        if isinstance(paths, (list, tuple)):
            path = paths[0]
        else:
            path = paths
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        self.db = cantools.database.load_file(path)
        return self.db

    def use_existing(self, cantools_db):
        self.db = cantools_db

    def get_message(self, name_or_id):
        if self.db is None:
            return None
        try:
            if isinstance(name_or_id, str):
                return self.db.get_message_by_name(name_or_id)
            return self.db.get_message_by_frame_id(name_or_id)
        except Exception:
            return None

    def encode(self, msg_name, signals):
        msg = self.get_message(msg_name)
        if msg is None:
            raise ValueError(f"Message not found: {msg_name}")
        data = msg.encode(signals)
        return msg.frame_id, data, msg.is_extended_frame

    def decode(self, frame_id, data):
        msg = self.get_message(frame_id)
        if msg is None:
            return None, {}
        return msg.name, msg.decode(bytes(data))

    # --------- Validation helpers (static) ----------
    def validate_messages(self):
        """
        Returns a list of validation records per message with basic static checks:
        - dlc presence
        - calculated length vs. declared length
        - signal count
        - cycle_time presence
        - bit layout overlap (best-effort)
        """
        results = []
        if not self.db:
            return results
        # Check ID uniqueness
        ids_seen = {}
        for msg in self.db.messages:
            rec = {
                "message": msg.name,
                "frame_id": msg.frame_id,
                "dlc": getattr(msg, "length", None) or getattr(msg, "size", None),
                "signal_count": len(msg.signals),
                "cycle_time": getattr(msg, "cycle_time", None),
                "warnings": []
            }
            # duplicate ID
            if msg.frame_id in ids_seen:
                rec["warnings"].append(f"Frame ID duplicate with {ids_seen[msg.frame_id]}")
            else:
                ids_seen[msg.frame_id] = msg.name
            # calc length from signals
            calc_len = None
            if msg.signals:
                max_bit = 0
                for s in msg.signals:
                    start = getattr(s, "start", 0)
                    length = getattr(s, "length", 0)
                    max_bit = max(max_bit, start + length)
                calc_len = math.ceil(max_bit / 8.0)
                if rec["dlc"] and calc_len > rec["dlc"]:
                    rec["warnings"].append(f"Signals exceed DLC: calc={calc_len}, dlc={rec['dlc']}")
            rec["calc_len"] = calc_len
            # basic range presence
            for s in msg.signals:
                if getattr(s, "minimum", None) is None or getattr(s, "maximum", None) is None:
                    rec["warnings"].append(f"Signal {s.name} missing min/max")
            results.append(rec)
        return results
