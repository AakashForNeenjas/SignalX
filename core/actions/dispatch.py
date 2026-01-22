from core.actions import can, gs, instr, load, os, ps, ramp, util


def _handle_ramp(action_name, params, ctx):
    if action_name.startswith("Line and Load Regulation"):
        return ramp.handle_line_load_action(action_name, params, ctx)
    return ramp.handle_ramp_action(action_name, params, ctx)


PREFIX_HANDLERS = {
    "RAMP": _handle_ramp,
    "GS": gs.handle_gs,
    "PS": ps.handle_ps,
    "CAN": can.handle_can,
    "OS": os.handle_os,
    "LOAD": load.handle_load,
    "INSTR": instr.handle_instr,
}


def dispatch_action(action, params, ctx):
    if " / " in action:
        prefix, action_name = [p.strip() for p in action.split("/", 1)]
        prefix = prefix.upper()
        handler = PREFIX_HANDLERS.get(prefix)
        if handler:
            return handler(action_name, params, ctx)
        msg = f"Unsupported action prefix: {prefix}"
        print(msg)
        return False, msg
    return util.handle_utility(action, params, ctx)
