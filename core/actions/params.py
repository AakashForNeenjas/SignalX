import json
from typing import Any, Dict, Iterable, Optional


def parse_json(params: Any, default: Any = None, strict: bool = False) -> Any:
    if params is None or params == "":
        return default if default is not None else {}
    if isinstance(params, (dict, list)):
        return params
    if isinstance(params, str):
        try:
            return json.loads(params)
        except Exception as exc:
            if strict:
                raise ValueError("Invalid JSON") from exc
            return default if default is not None else {}
    return params


def parse_json_dict(params: Any, default: Optional[Dict[str, Any]] = None, strict: bool = False) -> Dict[str, Any]:
    data = parse_json(params, default=default if default is not None else {}, strict=strict)
    if isinstance(data, dict):
        return data
    if strict:
        raise ValueError("Expected JSON object")
    return default if default is not None else {}


def parse_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return default
        if text.lower().startswith("0x"):
            return int(text, 16)
        return int(text)
    return default


def _strip_units(text: str, units: Iterable[str] | None) -> str:
    if not units:
        return text
    lowered = text.lower()
    for unit in units:
        unit_lower = unit.lower()
        if lowered.endswith(unit_lower):
            return text[: -len(unit)].strip()
    return text


def parse_number(
    value: Any,
    default: Optional[float] = None,
    key: Optional[str] = None,
    strip_units: Iterable[str] | None = None,
) -> Optional[float]:
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, dict):
        if key and key in value:
            return parse_number(value.get(key), default=default, key=None, strip_units=strip_units)
        if len(value) == 1:
            return parse_number(next(iter(value.values())), default=default, key=None, strip_units=strip_units)
        return default
    if isinstance(value, str):
        text = _strip_units(value.strip(), strip_units)
        try:
            return float(text)
        except Exception:
            try:
                data = parse_json(text, default=None, strict=True)
            except Exception:
                return default
            return parse_number(data, default=default, key=key, strip_units=strip_units)
    return default
