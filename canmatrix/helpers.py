import re


def detect_counter_checksum(msg, dlc_val=None):
    """
    Heuristic detection of counter and checksum signals in a DBC message.
    - Counters: name contains cnt/counter/ctr; stride=1; rollover=2^length
    - Checksums: name contains crc/checksum/chk; algo=sum8 if length<=8 else sum16; prefer if located in last byte(s)
    """
    counters = []
    checksums = []
    for sig in msg.signals:
        name_lower = sig.name.lower()
        # Counter detection
        if re.search(r"(cnt|ctr|counter)", name_lower):
            rollover = 2 ** getattr(sig, "length", 8)
            counters.append({"signal": sig.name, "stride": 1, "rollover": rollover})
        # Checksum detection
        if re.search(r"(crc|checksum|chk)", name_lower):
            algo = "sum8" if getattr(sig, "length", 8) <= 8 else "sum16"
            # Only add if appears to be in the last byte/word when dlc known
            start_byte = getattr(sig, "start", 0) // 8
            if dlc_val is None or start_byte >= max(0, (dlc_val or 1) - 1):
                checksums.append({"signal": sig.name, "algo": algo})
    return counters, checksums


def detect_mux_states(msg):
    """
    Return expected multiplexer states from a cantools message definition.
    """
    if not getattr(msg, "multiplexer_signal", None):
        return []
    states = set()
    for sig in msg.signals:
        if sig.is_multiplexer:
            continue
        if sig.multiplexer_ids:
            for mid in sig.multiplexer_ids:
                states.add(mid)
    return sorted(states)


def detect_plausibility_pairs(msg):
    """
    Heuristic plausibility pairs within a message.
    Example: Front_Speed vs Rear_Speed (<=20% diff).
    """
    pairs = []
    names = [s.name for s in msg.signals]
    if "Front_Speed" in names and "Rear_Speed" in names:
        pairs.append({"a": "Front_Speed", "b": "Rear_Speed", "tol_pct": 20.0})
    return pairs
