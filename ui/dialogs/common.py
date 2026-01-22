def parse_can_id(text: str) -> int:
    """Parse CAN ID from user input (hex like 0x123 or decimal). Raises ValueError on bad input."""
    if text is None:
        raise ValueError("Missing CAN ID")
    raw = str(text).strip()
    if not raw:
        raise ValueError("Missing CAN ID")
    if raw.lower().startswith("0x"):
        return int(raw, 16)
    return int(raw)


def format_line_load_summary(data: dict) -> str:
    gs = data.get("gs", {}) if isinstance(data, dict) else {}
    ps = data.get("ps", {}) if isinstance(data, dict) else {}
    dl = data.get("dl", {}) if isinstance(data, dict) else {}
    return (
        f"GS:{gs.get('start')}->{gs.get('end')} step {gs.get('step')} | "
        f"PS:{ps.get('start')}->{ps.get('end')} step {ps.get('step')} | "
        f"DL:{dl.get('start')}->{dl.get('end')} step {dl.get('step')}"
    )
