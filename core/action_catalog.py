import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from core.action_registry import INSTRUMENT_ACTIONS, CAN_ACTIONS, UTILITY_ACTIONS
from core.action_schemas import ACTION_PARAM_SCHEMAS


def _param_info(action_name: str, param_type: str) -> Dict[str, Any]:
    schema = ACTION_PARAM_SCHEMAS.get(action_name)
    if schema:
        return schema
    if param_type == "none":
        return {"type": "none"}
    if param_type == "float":
        return {"type": "float", "required": True}
    if param_type == "str":
        return {"type": "string", "required": True, "note": "Freeform string or JSON (see UI prompt)."}
    return {"type": param_type or "unknown"}


def _param_type(action_name: str, fallback: str) -> str:
    schema = ACTION_PARAM_SCHEMAS.get(action_name)
    if schema and isinstance(schema, dict):
        return schema.get("type", fallback)
    return fallback


def build_action_catalog() -> Dict[str, Any]:
    actions: List[Dict[str, Any]] = []

    for act in INSTRUMENT_ACTIONS:
        actions.append({
            "name": act.name,
            "group": act.group,
            "param_type": _param_type(act.name, act.param_type),
            "description": act.description or "",
            "params": _param_info(act.name, act.param_type),
        })

    for name in CAN_ACTIONS:
        actions.append({
            "name": name,
            "group": "CAN",
            "param_type": _param_type(name, "none"),
            "description": "",
            "params": _param_info(name, _param_type(name, "none")),
        })

    for name in UTILITY_ACTIONS:
        actions.append({
            "name": name,
            "group": "UTILITY",
            "param_type": _param_type(name, "none"),
            "description": "",
            "params": _param_info(name, _param_type(name, "none")),
        })

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "action_count": len(actions),
        "actions": actions,
    }


def write_action_catalog(output_path: str | None = None) -> str:
    catalog = build_action_catalog()
    if output_path:
        out_path = Path(output_path)
    else:
        out_path = Path.cwd() / "docs" / "ACTION_DEFINITIONS.json"
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=True))
        return str(out_path)
    except Exception:
        # Avoid breaking app startup if the path is not writable.
        return ""


if __name__ == "__main__":
    path = write_action_catalog()
    if path:
        print(f"Wrote action catalog: {path}")
